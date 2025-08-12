# 文件名: main.py

import sys
import threading
import webbrowser
from PyQt6.QtWidgets import QApplication
from waitress import serve

from app import create_app
from app.overlay import OverlayController

from app.inference import LOGITECH


def run_server_in_thread(flask_app, host, port):
    print(f"服务器线程: 正在启动 Waitress 服务器于 http://{host}:{port}")
    serve(flask_app, host=host, port=port, _quiet=True)


def main():
    # --- 1. 初始化 PyQt GUI (主线程) ---
    qt_app = QApplication(sys.argv)

    scaling_factor = qt_app.primaryScreen().devicePixelRatio()
    print(f"主线程: 检测到屏幕缩放比例为: {scaling_factor * 100:.0f}%")

    print("主线程: 正在尝试加载罗技驱动...")
    logitech_manager = LOGITECH()
    if not logitech_manager.state:
        print("主线程: 警告 - 罗技驱动加载失败。鼠标控制功能将不可用。")

    try:
        print("主线程: 正在初始化 OverlayController...")
        gui_controller = OverlayController()
        print("主线程: OverlayController 初始化成功。")
    except Exception as e:
        print(f"主线程: 初始化 OverlayController 失败，程序退出: {e}")
        return

    # --- 2. 创建 Flask 应用实例，并注入所有需要的共享对象 ---
    flask_app = create_app(
        gui_controller=gui_controller,
        scaling_factor=scaling_factor,
        logitech_manager=logitech_manager
    )

    # --- 3. 在后台线程中启动 Waitress 服务器 ---
    host = '127.0.0.1'
    port = 8000
    url = f"http://{host}:{port}"
    server_thread = threading.Thread(
        target=run_server_in_thread,
        args=(flask_app, host, port),
        daemon=True
    )
    server_thread.start()
    print(f"主线程: Web 服务器已在后台启动。")

    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"主线程: 自动打开浏览器失败: {e}。请手动访问 {url}")

    # --- 4. 启动 PyQt 事件循环 ---
    print("主线程: 启动 PyQt 事件循环。桌面覆盖层已激活。")
    sys.exit(qt_app.exec())


if __name__ == '__main__':
    main()