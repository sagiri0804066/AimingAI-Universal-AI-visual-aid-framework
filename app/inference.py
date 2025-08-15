# app/inference.py
import os
import time
import threading
import traceback
import numpy as np
import cv2
import mss
import torch
from ultralytics import YOLO
from pynput import keyboard
from PyQt6.QtCore import QRect

from app.mouse_control import MouseController
from app.drawing import DrawingController


def convert_hotkey_format(hotkey_str):
    if not hotkey_str: return ""
    hotkey_str = hotkey_str.lower().replace(' ', '')
    parts = hotkey_str.split('+')
    modifiers = {'alt', 'ctrl', 'shift', 'cmd'}
    key_map = {'caps': 'caps_lock', 'esc': 'esc', 'space': 'space', 'enter': 'enter', 'del': 'delete'}
    for i in range(1, 13): key_map[f'f{i}'] = f'f{i}'
    converted_parts = [f'<{p}>' if p in modifiers else key_map.get(p, p) for p in parts]
    return '+'.join(converted_parts)


class InferenceThread(threading.Thread):
    def __init__(self, config, mouse_controller: MouseController, drawing_controller: DrawingController,
                 scaling_factor=1.0):
        super().__init__()
        self.config = config
        self.daemon = True
        self._is_running = threading.Event()
        self._is_running.set()
        self.is_active = False
        self.scaling_factor = scaling_factor
        self.mouse_controller = mouse_controller
        self.drawing_controller = drawing_controller

        self.locked_target_id = None

        self.model, self.keyboard_listener, self.hotkey_target = None, None, None

    def stop(self):
        self._is_running.clear()

    def _on_hotkey_press(self):
        self.is_active = not self.is_active

    def _handle_single_key_press(self, key):
        key_str = getattr(key, 'char', getattr(key, 'name', None))
        if key_str == self.hotkey_target: self._on_hotkey_press()

    def run(self):
        try:
            if not self.mouse_controller.is_ready: return
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            model_path = os.path.join(self.config['models_dir'], self.config['model'])
            self.model = YOLO(model_path)
            self.model.to(device).fuse()
            print(f"YOLO 模型 '{self.config['model']}' 加载成功，设备: {device}")
            self.hotkey_target = convert_hotkey_format(self.config['hotkey'])
            print(f"推理线程: 热键设置为 '{self.hotkey_target}'")
            hotkey_map = {self.hotkey_target: self._on_hotkey_press}
            self.keyboard_listener = keyboard.GlobalHotKeys(
                hotkey_map) if '+' in self.hotkey_target else keyboard.Listener(on_press=self._handle_single_key_press)
            self.keyboard_listener.start()
            self._main_loop()
        except Exception:
            print("推理线程中发生严重错误:")
            traceback.print_exc()
        finally:
            self._cleanup()

    def _cleanup(self):
        print("推理线程: 开始清理资源...")
        if self.drawing_controller: self.drawing_controller.clear_display()
        if self.keyboard_listener: self.keyboard_listener.stop()
        if self.model: del self.model; torch.cuda.empty_cache()
        print("推理线程: 资源清理完毕。")

    def _main_loop(self):
        conf_thresh = float(self.config.get('confidenceThreshold', 0.5))
        # IOU 阈值现在由追踪器内部管理，这里可以不设置
        p_gain = int(self.config['aimSpeed']) / 200.0
        offset_x_pct, offset_y_pct = float(self.config['offsetX']), float(self.config['offsetY'])
        logical_w, logical_h = int(self.config['rangeWidth']), int(self.config['rangeHeight'])
        physical_w, physical_h = int(logical_w * self.scaling_factor), int(logical_h * self.scaling_factor)

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            p_screen_w, p_screen_h = monitor["width"], monitor["height"]
            l_screen_w, l_screen_h = int(p_screen_w / self.scaling_factor), int(p_screen_h / self.scaling_factor)
            cap_area = {"left": (p_screen_w - physical_w) // 2, "top": (p_screen_h - physical_h) // 2,
                        "width": physical_w, "height": physical_h}
            scope_center_x_p, scope_center_y_p = physical_w / 2.0, physical_h / 2.0
            screen_center_x, screen_center_y = p_screen_w / 2.0, p_screen_h / 2.0
            scope_qrect = QRect((l_screen_w - logical_w) // 2, (l_screen_h - logical_h) // 2, logical_w, logical_h)

            last_time = time.time()
            # 普通目标和锁定目标
            color_map = {'tracked': (0, 255, 0), 'locked': (255, 0, 0)}

            while self._is_running.is_set():
                frame = np.array(sct.grab(cap_area))

                # =================================================================
                # ==                  调用 model.track()               ==
                # =================================================================
                # persist=True 告诉追踪器帧与帧之间是连续的
                results = self.model.track(
                    source=cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR),
                    persist=True,
                    conf=conf_thresh,
                    tracker="bytetrack.yaml",  # 指定使用ByteTrack
                    verbose=False
                )
                # =================================================================

                current_time = time.time()
                fps = 1.0 / (current_time - last_time) if (current_time - last_time) > 0 else 0
                last_time = current_time

                all_targets = []
                # 检查是否有追踪结果
                if results[0].boxes.id is not None:
                    # 获取所有目标的框、ID和置信度
                    boxes_xyxy = results[0].boxes.xyxy.cpu().numpy()
                    track_ids = results[0].boxes.id.int().cpu().tolist()
                    confs = results[0].boxes.conf.cpu().numpy()

                    for box, tid, conf in zip(boxes_xyxy, track_ids, confs):
                        all_targets.append({'box': box, 'id': tid, 'conf': conf})

                # 检查之前锁定的目标是否还存在
                if self.locked_target_id and not any(t['id'] == self.locked_target_id for t in all_targets):
                    self.locked_target_id = None

                move_x, move_y = 0, 0
                locked_target_box = None
                if self.is_active:
                    # 如果没有锁定目标，则选择一个离准星最近的
                    if self.locked_target_id is None and all_targets:
                        min_dist_sq = float('inf')
                        best_target = None
                        for t in all_targets:
                            abs_center_x = cap_area["left"] + (t['box'][0] + t['box'][2]) / 2.0
                            abs_center_y = cap_area["top"] + (t['box'][1] + t['box'][3]) / 2.0
                            dist_sq = (abs_center_x - screen_center_x) ** 2 + (abs_center_y - screen_center_y) ** 2
                            if dist_sq < min_dist_sq:
                                min_dist_sq = dist_sq
                                best_target = t
                        if best_target:
                            self.locked_target_id = best_target['id']

                    # 如果有锁定的目标，计算移动
                    if self.locked_target_id:
                        locked_target = next((t for t in all_targets if t['id'] == self.locked_target_id), None)
                        if locked_target:
                            locked_target_box = locked_target['box']
                            x1, y1, x2, y2 = locked_target_box
                            target_x = (x1 + x2) / 2.0 + ((x2 - x1) * offset_x_pct / 100.0)
                            target_y = (y1 + y2) / 2.0 + ((y2 - y1) * offset_y_pct / 100.0)
                            error_x, error_y = target_x - scope_center_x_p, target_y - scope_center_y_p
                            move_x, move_y = int(error_x * p_gain), int(error_y * p_gain)
                else:
                    self.locked_target_id = None  # 未激活时，清除锁定

                self.mouse_controller.move_relative(move_x, move_y)

                target_items = []
                if self.config['enableDraw']:
                    for t in all_targets:
                        color = color_map['locked'] if t['id'] == self.locked_target_id else color_map['tracked']
                        x1_p, y1_p, x2_p, y2_p = t['box']
                        x1_l, y1_l = x1_p / self.scaling_factor, y1_p / self.scaling_factor
                        w_l, h_l = (x2_p - x1_p) / self.scaling_factor, (y2_p - y1_p) / self.scaling_factor
                        qrect = QRect(int(scope_qrect.left() + x1_l), int(scope_qrect.top() + y1_l), int(w_l), int(h_l))
                        target_items.append((qrect, color))

                status_text, status_color = (f"激活 FPS: {int(fps)}", (255, 0, 0)) if self.is_active else (
                f"暂停 FPS: {int(fps)}", (0, 255, 0))

                drawing_data = {
                    "scope_rect": scope_qrect,
                    "target_items": target_items,
                    "status_text": status_text,
                    "status_color": status_color,
                    "show_scope": self.config['showScope']
                }
                self.drawing_controller.update_tracked_display(drawing_data)