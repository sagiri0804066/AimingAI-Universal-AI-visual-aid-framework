# app/mouse_control.py
import os
import ctypes


class MouseController:
    """
    封装罗技驱动，提供独立的鼠标控制功能。
    负责加载驱动并提供简单的相对移动接口。
    """
    def __init__(self):
        """
        初始化鼠标控制器，加载罗技DLL。
        """
        self.dll = None
        self.is_ready = False
        try:
            # 假设DLL与此文件位于同一目录或在可访问的路径中
            dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logitech.driver.dll')
            if not os.path.exists(dll_path):
                print(f"错误：找不到DLL文件 '{dll_path}'")
                return

            self.dll = ctypes.CDLL(dll_path)
            # 尝试打开设备
            if self.dll.device_open() == 1:
                print("罗技驱动加载并打开成功。")
                # 为 moveR 函数设置参数类型
                self.dll.moveR.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_bool]
                self.dll.moveR.restype = None
                self.is_ready = True
            else:
                print("罗技驱动加载失败：无法打开设备。")
                self.dll = None # 释放引用
        except Exception as e:
            print(f"加载罗技DLL或打开设备时发生未知错误: {e}")
            self.dll = None

    def move_relative(self, dx: int, dy: int):
        """
        执行相对鼠标移动。

        参数:
            dx (int): X轴方向的移动距离。
            dy (int): Y轴方向的移动距离。
        """
        if not self.is_ready or (dx == 0 and dy == 0):
            return
        try:
            # 调用DLL中的 moveR 函数
            self.dll.moveR(dx, dy, True)
        except Exception as e:
            print(f"调用 moveR 时出错: {e}")

    def close(self):
        """
        如果DLL支持，则关闭设备句柄。
        """
        if self.is_ready and hasattr(self.dll, 'device_close'):
            print("正在关闭罗技设备。")
            self.dll.device_close()
        self.is_ready = False