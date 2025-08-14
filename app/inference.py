import os
import time
import threading
import ctypes
import traceback
import numpy as np
import cv2
import mss
import torch
from ultralytics import YOLO
from pynput import keyboard
from PyQt6.QtCore import QRect


def convert_hotkey_format(hotkey_str):
    """
    将用户友好的热键字符串 (如 'Alt+Caps') 转换为 pynput 可以解析的正确格式 (如 '<alt>+caps_lock')。
    """
    if not hotkey_str: return ""
    hotkey_str = hotkey_str.lower().replace(' ', '')
    parts = hotkey_str.split('+')
    modifiers = {'alt', 'ctrl', 'shift', 'cmd', 'win', 'command'}
    key_map = {
        'caps': 'caps_lock', 'capslock': 'caps_lock', 'esc': 'esc', 'space': 'space',
        'enter': 'enter', 'del': 'delete', 'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
        'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8', 'f9': 'f9', 'f10': 'f10',
        'f11': 'f11', 'f12': 'f12',
    }
    converted_parts = []
    for part in parts:
        if part in modifiers:
            pynput_part = part.replace('win', 'cmd').replace('command', 'cmd')
            converted_parts.append(f'<{pynput_part}>')
        elif part in key_map:
            converted_parts.append(key_map[part])
        else:
            converted_parts.append(part)
    return '+'.join(converted_parts)


class LOGITECH:
    """罗技驱动管理器，这个类的实例应该在主程序中创建一次。"""

    def __init__(self):
        self.dll, self.state = None, False
        try:
            dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logitech.driver.dll')
            if not os.path.exists(dll_path):
                print(f"错误：找不到DLL文件 '{dll_path}'")
                return
            self.dll = ctypes.CDLL(dll_path)
            self.state = self.dll.device_open() == 1
            if self.state:
                print("罗技驱动加载成功。")
                self.dll.moveR.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_bool]
                self.dll.moveR.restype = None
            else:
                print("罗技驱动加载失败。")
        except Exception as e:
            print(f"加载罗技DLL时出错: {e}")


class InferenceThread(threading.Thread):
    def __init__(self, config, gui_controller, logitech_manager, scaling_factor=1.0):
        super().__init__()
        self.config = config
        self.daemon = True
        self._is_running = threading.Event()
        self._is_running.set()
        self.is_active = False
        self.gui_controller = gui_controller
        self.scaling_factor = scaling_factor
        if not self.gui_controller:
            raise ValueError("InferenceThread 需要一个有效的 gui_controller 实例。")

        self.logitech = logitech_manager
        self.model, self.keyboard_listener, self.hotkey_target = None, None, None

    def stop(self):
        self._is_running.clear()

    def _on_hotkey_press(self):
        self.is_active = not self.is_active

    def _handle_single_key_press(self, key):
        """监听单键热键。"""
        try:
            key_str = key.char if hasattr(key, 'char') else key.name
        except AttributeError:
            return

        if key_str == self.hotkey_target:
            self._on_hotkey_press()

    def _calculate_iou(self, box1, box2):
        """计算两个边界框的交并比 (IOU)。Box格式: [x1, y1, x2, y2]"""
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])

        inter_area = max(0, x2_inter - x1_inter) * max(0, y2_inter - y1_inter)
        if inter_area == 0:
            return 0.0

        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = box1_area + box2_area - inter_area

        return inter_area / union_area

    def run(self):
        try:
            if not self.logitech or not self.logitech.state:
                print("错误：罗技驱动未就绪，推理线程无法启动。")
                self.stop()
                return

            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            model_path_full = os.path.join(self.config['models_dir'], self.config['model'])
            self.model = YOLO(model_path_full)
            self.model.to(device)
            self.model.fuse()
            print(f"YOLO 模型 '{self.config['model']}' 加载成功，使用设备: {device}")

            self.hotkey_target = convert_hotkey_format(self.config['hotkey'])
            print(f"推理线程: 热键设置为 '{self.hotkey_target}'")

            if '+' in self.hotkey_target:
                hotkey_combination = keyboard.HotKey(
                    keyboard.HotKey.parse(self.hotkey_target), self._on_hotkey_press)
                self.keyboard_listener = keyboard.Listener(
                    on_press=hotkey_combination.press, on_release=hotkey_combination.release)
            else:
                self.keyboard_listener = keyboard.Listener(on_press=self._handle_single_key_press)

            self.keyboard_listener.start()
            print("推理线程: 键盘监听器启动成功。")
            self._main_loop()

        except Exception:
            print("推理线程中发生严重错误，详细信息如下:")
            traceback.print_exc()
        finally:
            self._cleanup()

    def _cleanup(self):
        print("推理线程: 开始清理资源...")
        if self.gui_controller:
            clear_data = {"scope_rect": QRect(), "target_boxes": [], "status_text": "", "color": (0, 0, 0),
                          "show_scope": False}
            self.gui_controller.post_data_for_drawing(clear_data)
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.model:
            del self.model
            torch.cuda.empty_cache()
        print("推理线程: 资源清理完毕。")

    def _main_loop(self):
        # --- 核心参数 ---
        logical_w = int(self.config['rangeWidth'])
        logical_h = int(self.config['rangeHeight'])
        physical_w = int(logical_w * self.scaling_factor)
        physical_h = int(logical_h * self.scaling_factor)
        aim_speed = int(self.config['aimSpeed'])
        offset_x_pct = float(self.config['offsetX'])
        offset_y_pct = float(self.config['offsetY'])
        show_scope = self.config['showScope']
        enable_draw = self.config['enableDraw']
        p_gain = aim_speed / 200.0

        # --- 优化参数  ---
        move_deadzone = 1.5
        iou_track_threshold = 0.4

        # --- 高级推理参数 ---
        conf_threshold = float(self.config.get('confidenceThreshold', 0.5))
        iou_threshold = float(self.config.get('iouThreshold', 0.45))
        max_detections = int(self.config.get('maxDetection', 100))
        image_size = int(self.config.get('imageSize', 640))
        use_fp16 = bool(self.config.get('fp16', True))
        use_augment = bool(self.config.get('augment', False))

        print(
            f"推理参数: Conf={conf_threshold}, IOU={iou_threshold}, MaxDet={max_detections}, ImgSz={image_size}, FP16={use_fp16}, Augment={use_augment}")

        # --- 状态变量 ---
        locked_target_box = None

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            physical_screen_w, physical_screen_h = monitor["width"], monitor["height"]
            logical_screen_w = int(physical_screen_w / self.scaling_factor)
            logical_screen_h = int(physical_screen_h / self.scaling_factor)

            # 定义截图区域和其中心点
            capture_area = {"left": (physical_screen_w - physical_w) // 2, "top": (physical_screen_h - physical_h) // 2,
                            "width": physical_w, "height": physical_h}
            scope_center_x_p = physical_w / 2.0
            scope_center_y_p = physical_h / 2.0

            # 定义真正的屏幕中心点 (用于索敌)
            screen_center_x = physical_screen_w / 2.0
            screen_center_y = physical_screen_h / 2.0

            scope_qrect = QRect((logical_screen_w - logical_w) // 2, (logical_screen_h - logical_h) // 2, logical_w,
                                logical_h)

            last_time = time.time()
            while self._is_running.is_set():
                sct_img = sct.grab(capture_area)
                frame = np.array(sct_img)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                results = self.model(frame_bgr, verbose=False, conf=conf_threshold, iou=iou_threshold,
                                     max_det=max_detections, imgsz=image_size, half=use_fp16, augment=use_augment)

                all_boxes_xyxy_p = results[0].boxes.xyxy.cpu().numpy()

                target_boxes_qrects = []
                if enable_draw:
                    for box_p in all_boxes_xyxy_p:
                        x1_p, y1_p, x2_p, y2_p = box_p
                        x1_l, y1_l = x1_p / self.scaling_factor, y1_p / self.scaling_factor
                        w_l, h_l = (x2_p - x1_p) / self.scaling_factor, (y2_p - y1_p) / self.scaling_factor
                        final_x, final_y = scope_qrect.left() + x1_l, scope_qrect.top() + y1_l
                        if w_l > 0 and h_l > 0:
                            target_boxes_qrects.append(QRect(int(final_x), int(final_y), int(w_l), int(h_l)))

                if self.is_active:
                    current_best_target_p = None

                    if locked_target_box is not None and len(all_boxes_xyxy_p) > 0:
                        best_iou = 0
                        candidate_target = None
                        for box_p in all_boxes_xyxy_p:
                            iou = self._calculate_iou(locked_target_box, box_p)
                            if iou > best_iou:
                                best_iou = iou
                                candidate_target = box_p

                        if best_iou > iou_track_threshold:
                            current_best_target_p = candidate_target
                            locked_target_box = candidate_target
                        else:
                            locked_target_box = None

                    if current_best_target_p is None and len(all_boxes_xyxy_p) > 0:
                        min_dist_sq = float('inf')
                        # 遍历所有检测框
                        for box_p in all_boxes_xyxy_p:
                            # 计算检测框在截图区域内的中心点
                            center_x_p_relative = (box_p[0] + box_p[2]) / 2.0
                            center_y_p_relative = (box_p[1] + box_p[3]) / 2.0

                            # 将其转换为在整个屏幕上的绝对坐标
                            abs_center_x = capture_area["left"] + center_x_p_relative
                            abs_center_y = capture_area["top"] + center_y_p_relative

                            # 计算与屏幕中心的距离
                            dist_sq = (abs_center_x - screen_center_x) ** 2 + (abs_center_y - screen_center_y) ** 2

                            if dist_sq < min_dist_sq:
                                min_dist_sq = dist_sq
                                current_best_target_p = box_p

                        if current_best_target_p is not None:
                            locked_target_box = current_best_target_p

                    if current_best_target_p is not None:
                        x1_p, y1_p, x2_p, y2_p = current_best_target_p
                        box_w_p, box_h_p = x2_p - x1_p, y2_p - y1_p

                        target_point_x_p = (x1_p + x2_p) / 2.0 + (box_w_p * offset_x_pct / 100.0)
                        target_point_y_p = (y1_p + y2_p) / 2.0 + (box_h_p * offset_y_pct / 100.0)

                        error_x = target_point_x_p - scope_center_x_p
                        error_y = target_point_y_p - scope_center_y_p

                        if abs(error_x) > move_deadzone or abs(error_y) > move_deadzone:
                            move_x = int(error_x * p_gain)
                            move_y = int(error_y * p_gain)
                            if abs(move_x) > 0 or abs(move_y) > 0:
                                self.logitech.dll.moveR(move_x, move_y, True)
                    else:
                        locked_target_box = None
                else:
                    locked_target_box = None

                current_time = time.time()
                fps = 1.0 / (current_time - last_time) if (current_time - last_time) > 0 else 0
                last_time = current_time
                status_text, draw_color = (f"激活 FPS: {int(fps)}", (255, 0, 0)) if self.is_active else (
                f"暂停 FPS: {int(fps)}", (0, 255, 0))
                drawing_data = {"scope_rect": scope_qrect, "target_boxes": target_boxes_qrects,
                                "status_text": status_text, "color": draw_color, "show_scope": show_scope}
                self.gui_controller.post_data_for_drawing(drawing_data)