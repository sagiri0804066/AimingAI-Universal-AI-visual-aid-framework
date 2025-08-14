# 文件名: app/__init__.py

import os
import json
from flask import Flask


def create_app(gui_controller=None, scaling_factor=1.0, logitech_manager=None):
    """创建一个配置好的Flask应用实例。"""
    app = Flask(__name__, static_url_path='', static_folder='static/web')

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app.config['MODELS_DIR'] = os.path.join(project_root, 'models')
    app.config['CONFIG_FILE'] = os.path.join(project_root, 'config.json')

    # --- 存储所有共享对象 ---
    app.config['GUI_CONTROLLER'] = gui_controller
    app.config['SCALING_FACTOR'] = scaling_factor
    app.config['LOGITECH_MANAGER'] = logitech_manager

    # --- 日志部分 ---
    if gui_controller:
        print(f"Flask应用: GUI 控制器已附加, 缩放比例: {scaling_factor}")
    else:
        print("Flask应用: 在无GUI模式下运行。")

    # 加关于罗技驱动的日志，方便调试
    if logitech_manager and logitech_manager.state:
        print("Flask应用: 罗技驱动管理器已成功附加。")
    else:
        print("Flask应用: 在无罗技驱动模式下运行 (或驱动加载失败)。")

    os.makedirs(app.config['MODELS_DIR'], exist_ok=True)
    if not os.path.exists(app.config['CONFIG_FILE']):
        print(f"配置文件不存在，正在创建默认配置...")
        default_config = {
            "model": "MRZH.pt",
            "hotkey": "CapsLock",
            "rangeWidth": "320",
            "rangeHeight": "320",
            "aimSpeed": "20",
            "offsetX": "0",
            "offsetY": "0",
            "confidenceThreshold": "0.30",
            "iouThreshold": "0.45",
            "maxDetection": "10",
            "imageSize": "640",
            "showScope": True,
            "enableDraw": True,
            "fp16": True,
            "augment": False
        }
        with open(app.config['CONFIG_FILE'], 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)

    from . import routes
    app.register_blueprint(routes.bp)

    return app