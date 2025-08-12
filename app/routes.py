import os
import glob
import json
from flask import Blueprint, jsonify, request, current_app, send_from_directory

# 更新导入
from .inference import InferenceThread

bp = Blueprint('main', __name__)

# 全局变量
inference_thread = None


# --- API Endpoints ---

@bp.route('/api/models', methods=['GET'])
def get_models():
    """扫描模型目录并返回模型列表。"""
    models_dir = current_app.config['MODELS_DIR']
    model_files = glob.glob(os.path.join(models_dir, '*.pt')) + \
                  glob.glob(os.path.join(models_dir, '*.onnx'))

    models_data = {}
    for model_path in model_files:
        filename = os.path.basename(model_path)
        try:
            file_size_mb = os.path.getsize(model_path) / (1024 * 1024)
            models_data[filename] = {
                'name': os.path.splitext(filename)[0],
                'size': f"{file_size_mb:.2f} MB"
            }
        except OSError as e:
            print(f"无法访问文件 {filename}: {e}")
            continue

    return jsonify(models_data)


@bp.route('/api/models', methods=['POST'])
def upload_model_file():
    """处理模型文件上传。"""
    if 'model' not in request.files:
        return jsonify({'error': '请求中缺少模型文件部分'}), 400

    file = request.files['model']
    if file.filename == '':
        return jsonify({'error': '未选择任何文件'}), 400

    if file:
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['MODELS_DIR'], filename)
        file.save(filepath)
        print(f"模型已保存: {filepath}")
        return jsonify({'success': True, 'filename': filename})


@bp.route('/api/models/<string:filename>', methods=['DELETE'])
def delete_model_file(filename):
    """删除指定的模型文件。"""
    from werkzeug.utils import secure_filename
    filename = secure_filename(filename)  # 安全检查
    filepath = os.path.join(current_app.config['MODELS_DIR'], filename)

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"模型已删除: {filepath}")
            return jsonify({'success': True}), 200
        except OSError as e:
            print(f"删除模型失败 {filepath}: {e}")
            return jsonify({'error': '删除文件时发生服务器内部错误'}), 500
    else:
        return jsonify({'error': '文件未找到'}), 404


@bp.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """处理配置文件的读取和写入。"""
    config_file = current_app.config['CONFIG_FILE']

    if request.method == 'POST':
        try:
            config_data = request.json
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            print("配置已更新。")
            return jsonify({'success': True})
        except Exception as e:
            print(f"写入配置失败: {e}")
            return jsonify({'error': '保存配置时发生错误'}), 500
    else:  # GET
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return jsonify(config_data)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"读取配置失败: {e}. 可能文件已损坏或不存在。")
            return jsonify({'error': '无法读取配置文件'}), 500


@bp.route('/api/inference/start', methods=['POST'])
def start_inference_thread():
    """启动推理线程。"""
    global inference_thread

    if inference_thread and inference_thread.is_alive():
        return jsonify({'status': 'error', 'message': '推理任务已在运行中。'}), 409

    config = request.json
    config['models_dir'] = current_app.config['MODELS_DIR']

    # --- 从 app.config 中获取所有共享的实例 ---
    gui_controller = current_app.config.get('GUI_CONTROLLER')
    scaling_factor = current_app.config.get('SCALING_FACTOR', 1.0)
    logitech_manager = current_app.config.get('LOGITECH_MANAGER')  # 获取罗技驱动实例

    # --- 健壮性检查 ---
    if not gui_controller:
        return jsonify({'status': 'error', 'message': 'GUI控制器不可用。'}), 500

    if not logitech_manager or not logitech_manager.state:
        # 如果驱动未加载成功，则拒绝启动并告知前端
        return jsonify({'status': 'error', 'message': '罗技驱动未就绪，无法启动推理。'}), 503  # 503 Service Unavailable

    try:
        inference_thread = InferenceThread(
            config=config,
            gui_controller=gui_controller,
            logitech_manager=logitech_manager,
            scaling_factor=scaling_factor
        )
        inference_thread.start()
        print("路由: 启动推理指令已发送。",config)
        return jsonify({'status': 'success', 'message': '推理任务已启动。'}), 202
    except Exception as e:
        print(f"路由: 启动推理线程失败: {e}")
        return jsonify({'status': 'error', 'message': f'启动时发生错误: {e}'}), 500


@bp.route('/api/inference/stop', methods=['POST'])
def stop_inference_thread():
    """停止推理线程。"""
    global inference_thread

    if not inference_thread or not inference_thread.is_alive():
        return jsonify({'status': 'error', 'message': '没有正在运行的推理任务。'}), 404
    try:
        print("路由: 收到停止推理指令。")
        inference_thread.stop()
        inference_thread.join(timeout=5.0)
        inference_thread = None
        return jsonify({'status': 'success', 'message': '推理任务已成功停止。'}), 200
    except Exception as e:
        print(f"路由: 停止线程时出错: {e}")
        return jsonify({'status': 'error', 'message': f'停止时发生错误: {e}'}), 500

# --- 静态文件服务路由---
@bp.route('/')
def index():
    return send_from_directory(current_app.static_folder, 'index.html')