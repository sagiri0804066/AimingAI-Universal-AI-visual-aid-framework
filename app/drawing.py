# app/drawing.py
from PyQt6.QtCore import QRect


class DrawingController:
    """
    封装与GUI绘图相关的逻辑。
    它接收绘图数据，并将其传递给GUI线程进行渲染。
    """

    def __init__(self, gui_update_callback):
        if not callable(gui_update_callback):
            raise TypeError("gui_update_callback 必须是一个可调用对象")
        self.update_callback = gui_update_callback

    def update_tracked_display(self, drawing_data: dict):
        """
        准备包含多个带颜色目标的数据并请求GUI更新。
        这是为“响尾蛇”算法定制的新方法。

        期望的 'drawing_data' 格式:
        {
            "scope_rect": QRect,
            "target_items": [(QRect, (r, g, b)), (QRect, (r, g, b)), ...],
            "status_text": str,
            "status_color": (r, g, b),
            "show_scope": bool
        }
        """
        # 直接通过回调将数据发送到GUI线程
        self.update_callback(drawing_data)

    def clear_display(self):
        """请求GUI清除所有绘图元素。"""
        clear_data = {
            "scope_rect": QRect(),
            "target_items": [],
            "status_text": "",
            "status_color": (0, 0, 0),
            "show_scope": False
        }
        self.update_callback(clear_data)