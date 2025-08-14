import os
import sys
import subprocess
import zipfile
import urllib.request
import time

# --- 配置 ---
# 嵌入式Python包的文件名
EMBEDDED_PYTHON_ZIP = "python-3.10.11-embed-amd64.zip"
# 解压后存放迷你Python的文件夹名
RUNTIME_DIR = "python-runtime"
# 要执行的部署脚本
DEPLOY_SCRIPT = "deploy.py"


class Color:
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


def print_color(text, color):
    print(f"{color}{text}{Color.ENDC}")


def get_base_path():
    """获取程序运行时的基本路径，兼容PyInstaller"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe
        return os.path.dirname(sys.executable)
    else:
        # 如果是直接运行的 .py
        return os.path.dirname(os.path.abspath(__file__))


def setup_embedded_python(base_path):
    """检查并配置嵌入式Python环境，返回python.exe的路径"""
    runtime_path = os.path.join(base_path, RUNTIME_DIR)
    python_exe = os.path.join(runtime_path, "python.exe")
    zip_path = os.path.join(base_path, EMBEDDED_PYTHON_ZIP)

    if os.path.exists(python_exe):
        print_color(f"[*] 找到本地Python运行时: {runtime_path}", Color.OKBLUE)
        return python_exe

    print_color("[!] 未找到本地Python运行时，正在为您配置...", Color.WARNING)

    if not os.path.exists(zip_path):
        print_color(f"[x] 致命错误: 找不到嵌入式Python包 '{EMBEDDED_PYTHON_ZIP}'!", Color.FAIL)
        return None

    # 1. 解压
    print_color(f"[*] 正在解压 '{EMBEDDED_PYTHON_ZIP}'...", Color.OKBLUE)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(runtime_path)
    except Exception as e:
        print_color(f"[x] 解压失败: {e}", Color.FAIL)
        return None

    # 2. 启用 site-packages (让pip可以安装模块)
    # 找到 pth 文件，如 python310._pth
    pth_files = [f for f in os.listdir(runtime_path) if f.endswith('._pth')]
    if pth_files:
        pth_file_path = os.path.join(runtime_path, pth_files[0])
        with open(pth_file_path, 'r+') as f:
            content = f.read()
            if "#import site" in content:
                print_color("[*] 正在启用 pip 支持...", Color.OKBLUE)
                f.seek(0)
                f.write(content.replace("#import site", "import site"))

    # 3. 安装 pip
    print_color("[*] 正在为本地Python安装pip...", Color.OKBLUE)
    get_pip_path = os.path.join(runtime_path, "get-pip.py")
    try:
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip_path)
        subprocess.check_call([python_exe, get_pip_path])
        os.remove(get_pip_path)  # 清理
        print_color("[+] pip 安装成功！", Color.OKGREEN)
    except Exception as e:
        print_color(f"[x] pip 安装失败: {e}", Color.FAIL)
        return None

    print_color("\n[+] 本地Python运行时配置完成！", Color.OKGREEN)
    return python_exe


def main():
    """启动器主函数"""
    print_color("=" * 40, Color.OKGREEN)
    print_color("  环境部署启动器已启动", Color.OKGREEN)
    print_color("  将自动为您准备所需环境，请稍候...", Color.OKGREEN)
    print_color("=" * 40, Color.OKGREEN)

    base_path = get_base_path()
    os.chdir(base_path)  # 确保工作目录正确

    python_executable = setup_embedded_python(base_path)

    if not python_executable:
        print_color("\n[x] 部署失败：无法初始化Python环境。", Color.FAIL)
        time.sleep(10)
        sys.exit(1)

    deploy_script_path = os.path.join(base_path, DEPLOY_SCRIPT)
    if not os.path.exists(deploy_script_path):
        print_color(f"\n[x] 致命错误: 找不到部署脚本 '{DEPLOY_SCRIPT}'!", Color.FAIL)
        time.sleep(10)
        sys.exit(1)

    print_color("\n[*] 准备就绪，正在启动主部署流程...", Color.OKGREEN)
    print_color("-" * 40, Color.OKGREEN)

    try:
        # 使用我们自己的Python来运行部署脚本
        subprocess.run([python_executable, deploy_script_path], check=True)
    except subprocess.CalledProcessError:
        print_color("\n[x] 部署脚本执行失败！请检查上方日志获取详细信息。", Color.FAIL)
    except Exception as e:
        print_color(f"\n[x] 发生未知错误: {e}", Color.FAIL)

    # 给用户时间查看最终信息
    print("\n按任意键退出启动器...")
    if os.name == 'nt':
        os.system('pause > nul')


if __name__ == "__main__":
    main()