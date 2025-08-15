import os
import sys
import threading
import webbrowser

# 将项目根目录添加到Python的模块搜索路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import QApplication
from waitress import serve

# 导入重构后的新模块和相关组件
from app import create_app
from app.overlay import OverlayController
from app.mouse_control import MouseController
from app.drawing import DrawingController


def run_server_in_thread(flask_app, host, port):
    """在后台线程中运行Flask服务器。"""
    # 使用 Waitress 作为生产环境的WSGI服务器
    serve(flask_app, host=host, port=port, _quiet=True)


def main():
    """应用程序主入口点。"""
    # 1. 初始化GUI应用和核心组件
    qt_app = QApplication(sys.argv)
    # 获取屏幕缩放因子，这是进行坐标转换的关键
    scaling_factor = qt_app.primaryScreen().devicePixelRatio()

    # 2. 初始化独立的控制器模块
    # 初始化鼠标控制器，它封装了所有罗技驱动的交互
    mouse_controller = MouseController()
    if not mouse_controller.is_ready:
        print("警告: 鼠标控制器初始化失败，相关功能将不可用。")

    # 初始化桌面覆盖层（GUI窗口）
    try:
        overlay_controller = OverlayController()
    except Exception as e:
        print(f"错误: 初始化OverlayController失败，程序退出: {e}")
        return

    # 初始化绘图控制器，并将GUI的更新方法作为回调函数传递进去
    # 这样，DrawingController就可以请求GUI进行绘制，而无需知道GUI的具体实现
    gui_callback = overlay_controller.post_data_for_drawing
    drawing_controller = DrawingController(gui_update_callback=gui_callback)

    # 3. 创建Flask应用实例并注入新的控制器依赖
    # Flask后端将接收这些控制器，并在启动推理任务时将它们传递给InferenceThread
    flask_app = create_app(
        mouse_controller=mouse_controller,
        drawing_controller=drawing_controller,
        scaling_factor=scaling_factor
    )

    # 4. 在后台启动Web服务器
    host = '127.0.0.1'
    port = 8000
    url = f"http://{host}:{port}"

    server_thread = threading.Thread(
        target=run_server_in_thread,
        args=(flask_app, host, port),
        daemon=True  # 守护线程确保主程序退出时它也退出
    )
    server_thread.start()

    # 5. 自动在浏览器中打开Web界面
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"提示: 自动打开浏览器失败: {e}。请手动访问 {url}")

    # 6. 启动PyQt事件循环，激活桌面覆盖层
    print("信息: 应用程序已启动，桌面覆盖层已激活。")
    sys.exit(qt_app.exec())


if __name__ == '__main__':
    main()