# app/overlay.py
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QRect, QPoint


class OverlayWindow(QWidget):
    """一个透明的、可点击穿透的覆盖窗口。"""

    def __init__(self, screen_geometry):
        super().__init__()
        self.setGeometry(screen_geometry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 绘图数据
        self._scope_rect = QRect()
        # **修改**: 现在存储 (QRect, (r,g,b)) 元组的列表
        self._target_items = []
        self._status_text = ""
        self._status_color = QColor(0, 255, 0)
        self._font = QFont("Arial", 12, QFont.Weight.Bold)
        self._show_scope = True

    def paintEvent(self, event):
        """当窗口需要重绘时自动调用。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._font)

        # 绘制状态文本和范围框
        if self._show_scope and not self._scope_rect.isNull():
            pen = QPen(self._status_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(self._scope_rect)
            painter.drawText(self._scope_rect.topLeft() + QPoint(5, 20), self._status_text)

        # **修改**: 遍历并绘制带独立颜色的目标框
        if self._target_items:
            pen = QPen()
            pen.setWidth(2)
            for rect, color_tuple in self._target_items:
                pen.setColor(QColor(*color_tuple))
                painter.setPen(pen)
                painter.drawRect(rect)

    @pyqtSlot(dict)
    def receive_drawing_data(self, data):
        """这是一个槽函数，它会在GUI线程中被安全地调用。"""
        self._scope_rect = data.get('scope_rect', QRect())
        # **修改**: 获取新的数据结构
        self._target_items = data.get('target_items', [])
        self._status_text = data.get('status_text', "")
        self._status_color.setRgb(*data.get('status_color', (0, 255, 0)))
        self._show_scope = data.get('show_scope', True)
        self.update()  # 请求重绘


class OverlayController(QObject):
    """管理GUI，并提供与工作线程之间的线程安全通信。"""
    update_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._app = QApplication.instance()
        if not self._app:
            raise RuntimeError("OverlayController必须在QApplication创建后实例化。")

        screen_geometry = self._app.primaryScreen().geometry()
        self._window = OverlayWindow(screen_geometry)
        self.update_signal.connect(self._window.receive_drawing_data)
        self._window.show()

    def post_data_for_drawing(self, data):
        """工作线程将调用此方法来安全地发送绘图数据。"""
        self.update_signal.emit(data)