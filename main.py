import os
import sys
import threading
import webbrowser

# 将项目根目录添加到Python的模块搜索路径中，以解决模块导入问题
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import QApplication
from waitress import serve

from app import create_app
from app.overlay import OverlayController
from app.inference import LOGITECH


def run_server_in_thread(flask_app, host, port):
    """在后台线程中运行Flask服务器。"""
    # 使用 Waitress 作为生产环境的WSGI服务器
    serve(flask_app, host=host, port=port, _quiet=True)


def main():
    """应用程序主入口点。"""
    # 1. 初始化GUI应用和核心组件
    qt_app = QApplication(sys.argv)
    scaling_factor = qt_app.primaryScreen().devicePixelRatio()

    # 尝试加载罗技驱动
    logitech_manager = LOGITECH()
    if not logitech_manager.state:
        print("警告: 罗技驱动加载失败，相关功能将不可用。")

    # 初始化桌面覆盖层控制器
    try:
        gui_controller = OverlayController()
    except Exception as e:
        print(f"错误: 初始化OverlayController失败，程序退出: {e}")
        return

    # 2. 创建Flask应用实例并注入依赖
    flask_app = create_app(
        gui_controller=gui_controller,
        scaling_factor=scaling_factor,
        logitech_manager=logitech_manager
    )

    # 3. 在后台启动Web服务器
    host = '127.0.0.1'
    port = 8000
    url = f"http://{host}:{port}"

    server_thread = threading.Thread(
        target=run_server_in_thread,
        args=(flask_app, host, port),
        daemon=True  # 设置为守护线程，确保主程序退出时该线程也退出
    )
    server_thread.start()

    # 4. 自动在浏览器中打开Web界面
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"提示: 自动打开浏览器失败: {e}。请手动访问 {url}")

    # 5. 启动PyQt事件循环，激活桌面覆盖层
    print("信息: 应用程序已启动，桌面覆盖层已激活。")
    sys.exit(qt_app.exec())


if __name__ == '__main__':
    main()