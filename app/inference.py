# 文件名: inference.py

import os, time, threading, ctypes, numpy as np, cv2, mss, torch, traceback
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
            if not os.path.exists(dll_path): print(f"错误：找不到DLL文件 '{dll_path}'"); return
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
        if not self.gui_controller: raise ValueError("InferenceThread 需要一个有效的 gui_controller 实例。")

        # 使用从外部传入的罗技驱动管理器
        self.logitech = logitech_manager
        self.model, self.keyboard_listener, self.hotkey = None, None, None

    def stop(self):
        self._is_running.clear()

    def _on_hotkey_press(self):
        self.is_active = not self.is_active

    def _handle_single_key_press(self, key):
        """用于监听所有按键，并与我们的单键热键目标进行比较。"""
        key_str = ""
        try:
            key_str = key.name
        except AttributeError:
            key_str = key.char

        # 检查按下的键是否是我们的目标热键
        if key_str == self.hotkey_target:
            self._on_hotkey_press()

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
            print(f"YOLO 模型 '{self.config['model']}' 加载成功。")

            user_hotkey = self.config['hotkey']
            # 使用我们已经验证过的转换函数
            self.hotkey_target = convert_hotkey_format(user_hotkey)
            print(f"推理线程: 用户热键 '{user_hotkey}' -> 转换为 '{self.hotkey_target}'")

            # 根据热键类型选择不同的监听方式
            if '+' in self.hotkey_target:
                print("推理线程: 检测到组合键，使用 HotKey 模式。")
                hotkey_combination = keyboard.HotKey(
                    keyboard.HotKey.parse(self.hotkey_target),
                    self._on_hotkey_press
                )
                self.keyboard_listener = keyboard.Listener(
                    on_press=hotkey_combination.press,
                    on_release=hotkey_combination.release
                )
            else:
                print("推理线程: 检测到单键，使用常规 Listener 模式。")
                self.keyboard_listener = keyboard.Listener(
                    on_press=self._handle_single_key_press
                )

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
            clear_data = {
                "scope_rect": QRect(),
                "target_boxes": [],
                "status_text": "",
                "color": (0, 0, 0),
                "show_scope": False
            }
            self.gui_controller.post_data_for_drawing(clear_data)
        if self.keyboard_listener: self.keyboard_listener.stop()
        if self.model: del self.model; torch.cuda.empty_cache()
        print("推理线程: 资源清理完毕。")

    def _main_loop(self):
        logical_w = int(self.config['rangeWidth'])
        logical_h = int(self.config['rangeHeight'])

        physical_w = int(logical_w * self.scaling_factor)
        physical_h = int(logical_h * self.scaling_factor)

        # 从配置中获取其他参数
        aim_speed = int(self.config['aimSpeed'])
        offset_x_pct = float(self.config['offsetX'])
        offset_y_pct = float(self.config['offsetY'])
        show_scope = self.config['showScope']
        enable_draw = self.config['enableDraw']
        p_gain = aim_speed / 200.0

        with mss.mss() as sct:
            # 获取主显示器的完整物理和逻辑尺寸
            monitor = sct.monitors[1]
            physical_screen_w, physical_screen_h = monitor["width"], monitor["height"]
            logical_screen_w = int(physical_screen_w / self.scaling_factor)
            logical_screen_h = int(physical_screen_h / self.scaling_factor)

            capture_area = {
                "left": (physical_screen_w - physical_w) // 2,
                "top": (physical_screen_h - physical_h) // 2,
                "width": physical_w,
                "height": physical_h
            }
            # 截图区域的物理中心点 (用于计算鼠标移动)
            scope_center_x_p = physical_w / 2.0
            scope_center_y_p = physical_h / 2.0

            scope_qrect = QRect(
                (logical_screen_w - logical_w) // 2,
                (logical_screen_h - logical_h) // 2,
                logical_w,
                logical_h
            )

            last_time = time.time()
            while self._is_running.is_set():
                sct_img = sct.grab(capture_area)
                frame = np.array(sct_img)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                results = self.model(frame_bgr, verbose=False, half=True, conf=0.5)

                target_boxes_qrects = []
                all_boxes = results[0].boxes

                # --- 坐标转换与绘图数据准备 ---
                if enable_draw:
                    for box in all_boxes:
                        x1_p, y1_p, x2_p, y2_p = box.xyxy[0].cpu().numpy()

                        x1_l = x1_p / self.scaling_factor
                        y1_l = y1_p / self.scaling_factor
                        w_l = (x2_p - x1_p) / self.scaling_factor
                        h_l = (y2_p - y1_p) / self.scaling_factor

                        final_x_on_screen = scope_qrect.left() + x1_l
                        final_y_on_screen = scope_qrect.top() + y1_l

                        if w_l > 0 and h_l > 0:
                            target_boxes_qrects.append(
                                QRect(int(final_x_on_screen), int(final_y_on_screen), int(w_l), int(h_l))
                            )

                if self.is_active:
                    best_target, min_dist = None, float('inf')
                    for box in all_boxes:
                        x1_p, y1_p, x2_p, y2_p = box.xyxy[0].cpu().numpy()
                        target_center_x_p = (x1_p + x2_p) / 2.0
                        target_center_y_p = (y1_p + y2_p) / 2.0
                        dist_sq = (target_center_x_p - scope_center_x_p) ** 2 + (
                                    target_center_y_p - scope_center_y_p) ** 2
                        if dist_sq < min_dist:
                            min_dist = dist_sq
                            best_target = box

                    if best_target:
                        x1_p, y1_p, x2_p, y2_p = best_target.xyxy[0].cpu().numpy()
                        box_w_p = x2_p - x1_p
                        box_h_p = y2_p - y1_p
                        target_point_x_p = (x1_p + x2_p) / 2.0 + (box_w_p * offset_x_pct / 100.0)
                        target_point_y_p = (y1_p + y2_p) / 2.0 + (box_h_p * offset_y_pct / 100.0)
                        error_x = target_point_x_p - scope_center_x_p
                        error_y = target_point_y_p - scope_center_y_p
                        move_x = int(error_x * p_gain)
                        move_y = int(error_y * p_gain)
                        if abs(move_x) > 0 or abs(move_y) > 0:
                            self.logitech.dll.moveR(move_x, move_y, True)

                current_time = time.time()
                fps = 1.0 / (current_time - last_time) if (current_time - last_time) > 0 else 0
                last_time = current_time
                status_text, draw_color = (f"激活 FPS: {int(fps)}", (255, 0, 0)) if self.is_active else (
                f"暂停 FPS: {int(fps)}", (0, 255, 0))
                drawing_data = {"scope_rect": scope_qrect, "target_boxes": target_boxes_qrects,
                                "status_text": status_text, "color": draw_color, "show_scope": show_scope}
                self.gui_controller.post_data_for_drawing(drawing_data)