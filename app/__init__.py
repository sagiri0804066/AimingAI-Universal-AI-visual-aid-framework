# 文件名: app/__init__.py

import os
import json
from flask import Flask

# 导入新的控制器类，以便进行类型检查
from .mouse_control import MouseController
from .drawing import DrawingController


def create_app(mouse_controller: MouseController = None, drawing_controller: DrawingController = None, scaling_factor=1.0):
    """
    创建一个配置好的Flask应用实例。

    现在接收 mouse_controller 和 drawing_controller 作为依赖项。
    """
    app = Flask(__name__, static_url_path='', static_folder='static/web')

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app.config['MODELS_DIR'] = os.path.join(project_root, 'models')
    app.config['CONFIG_FILE'] = os.path.join(project_root, 'config.json')

    # --- 存储所有共享对象 ---
    app.config['MOUSE_CONTROLLER'] = mouse_controller
    app.config['DRAWING_CONTROLLER'] = drawing_controller
    app.config['SCALING_FACTOR'] = scaling_factor

    # --- 更新日志部分以反映新的控制器 ---
    if drawing_controller:
        print(f"Flask应用: 绘图控制器已附加, 屏幕缩放比例: {scaling_factor}")
    else:
        print("Flask应用: 在无绘图控制器模式下运行。")

    if mouse_controller and mouse_controller.is_ready:
        print("Flask应用: 鼠标控制器已成功附加并就绪。")
    else:
        print("Flask应用: 在无鼠标控制器模式下运行 (或驱动加载失败)。")

    # --- 默认配置创建逻辑 ---
    os.makedirs(app.config['MODELS_DIR'], exist_ok=True)
    if not os.path.exists(app.config['CONFIG_FILE']):
        print(f"配置文件不存在，正在创建默认配置...")
        default_config = {
            "model": "MRZH.pt",
            "hotkey": "caps_lock",
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

    # 注册路由蓝图
    from . import routes
    app.register_blueprint(routes.bp)

    return app