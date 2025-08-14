import os
import sys
import subprocess
import platform
import time
import re

# --- 配置区 ---
RUNTIME_DIR = "python-runtime"
REQUIREMENTS_FILE = "requirements.txt"
MAIN_SCRIPT = "main.py"
SHORTCUT_NAME = "Aiming AI"
ICON_PATH = os.path.join("app", "static", "icon", "快捷图标.ico")


# --- 颜色定义 ---
class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_color(text, color):
    print(f"{color}{text}{Color.ENDC}")


# --- 核心功能函数 ---

def check_runtime_environment():
    """检查并确认我们的运行时环境"""
    print_color("\n--- 步骤 1: 检查本地Python运行时环境 ---", Color.HEADER)
    python_exe = sys.executable
    if RUNTIME_DIR in python_exe and os.path.exists(python_exe):
        print_color(f"[+] 成功使用本地运行时: {python_exe}", Color.OKGREEN)
        return True
    else:
        print_color(f"[x] 错误: 未能正确启动本地Python运行时。路径不正确: {python_exe}", Color.FAIL)
        return False


def get_pip_executable():
    """直接从当前运行的Python环境中定位pip"""
    python_dir = os.path.dirname(sys.executable)
    if platform.system() == "Windows":
        return os.path.join(python_dir, "Scripts", "pip.exe")
    else:
        return os.path.join(python_dir, "bin", "pip")


def install_dependencies():
    """第二步：安装项目依赖"""
    print_color("\n--- 步骤 2: 安装项目依赖 ---", Color.HEADER)

    if not os.path.exists(REQUIREMENTS_FILE):
        print_color(f"[x] 错误: 未找到依赖文件 '{REQUIREMENTS_FILE}'", Color.FAIL)
        return False

    pip_exec = get_pip_executable()
    if not os.path.exists(pip_exec):
        print_color(f"[x] 错误: 在运行时环境中未找到 pip: {pip_exec}", Color.FAIL)
        return False

    # 预先检测 requirements.txt 中 PyTorch 的 CUDA 版本
    cuda_version_suffix = ""
    try:
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r'torch==[.\d\w]+?\+(cu\d+)', line)
                if match:
                    cuda_version_suffix = match.group(1)  # 例如 'cu121'
                    break
    except Exception as e:
        print_color(f"[!] 读取依赖文件时发生警告: {e}", Color.WARNING)

    # 定义镜像策略：组合“高速PyPI镜像”和“高速PyTorch镜像”
    # 元组结构: (名称, PyPI主源, PyTorch额外源)
    mirror_strategies = [
        (
            "阿里/淘宝云镜像组合",
            "https://mirrors.aliyun.com/pypi/simple/",
            f"https://mirrors.aliyun.com/pytorch-wheels/{cuda_version_suffix}" if cuda_version_suffix else None
        ),
        (
            "清华大学镜像组合",
            "https://pypi.tuna.tsinghua.edu.cn/simple",
            f"https://pypi.tuna.tsinghua.edu.cn/simple"  # 清华源是统一的，本身就包含torch
        ),
        (
            "官方主站组合 (备用)",
            "https://pypi.org/simple",
            f"https://download.pytorch.org/whl/{cuda_version_suffix}" if cuda_version_suffix else None
        )
    ]

    for name, main_index_url, torch_extra_index_url in mirror_strategies:
        print_color(f"\n[*] 正在尝试使用 [{name}] 策略安装依赖...", Color.OKBLUE)

        command = [
            pip_exec, "install",
            "-r", REQUIREMENTS_FILE,
            "--index-url", main_index_url,
            "--trusted-host", main_index_url.split('//')[1].split('/')[0]
        ]

        # 如果当前策略包含一个有效的PyTorch额外源，就添加它
        if torch_extra_index_url:
            print_color(f"[*] 使用PyTorch专属源: {torch_extra_index_url}", Color.OKBLUE)
            command.extend(["--extra-index-url", torch_extra_index_url])
            command.extend(["--trusted-host", torch_extra_index_url.split('//')[1].split('/')[0]])

        try:
            result = subprocess.run(command, check=False)

            if result.returncode == 0:
                print_color(f"\n[+] 使用 [{name}] 成功安装所有依赖！", Color.OKGREEN)
                return True
            else:
                print_color(f"\n[!] 使用 [{name}] 策略失败，将尝试下一个策略。", Color.WARNING)
        except KeyboardInterrupt:
            print_color("\n[!] 用户中断了安装过程。", Color.WARNING)
            return False
        except Exception as e:
            print_color(f"\n[!] 执行 pip 命令时发生未知错误: {e}", Color.WARNING)

    print_color("\n[x] 所有镜像策略均尝试失败，依赖安装失败。", Color.FAIL)
    return False


def create_desktop_shortcut():
    """第三步: 创建桌面快捷方式 """
    print_color("\n--- 步骤 3: 创建桌面快捷方式 ---", Color.HEADER)

    if platform.system() != "Windows":
        print_color("[!] 当前系统不是 Windows，跳过创建桌面快捷方式。", Color.WARNING)
        return

    if not os.path.exists(MAIN_SCRIPT):
        print_color(f"[x] 错误: 主程序 '{MAIN_SCRIPT}' 不存在。", Color.FAIL)
        return

    shortcut_name_with_ext = f"{SHORTCUT_NAME}.lnk"
    target_exe = os.path.abspath(sys.executable)
    target_script = os.path.abspath(MAIN_SCRIPT)
    work_dir = os.path.abspath(os.path.dirname(MAIN_SCRIPT))
    icon_location = os.path.abspath(ICON_PATH) if os.path.exists(ICON_PATH) else ""

    print_color(f"[*] 准备在桌面创建快捷方式 '{shortcut_name_with_ext}'", Color.OKBLUE)

    try:
        ps_command = f"""
        # 动态获取当前用户的桌面路径，无论它在哪里
        $DesktopPath = [System.Environment]::GetFolderPath('Desktop')
        $ShortcutPath = Join-Path -Path $DesktopPath -ChildPath "{shortcut_name_with_ext}"

        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = "{target_exe}"
        $Shortcut.Arguments = '"{target_script}"'
        $Shortcut.WorkingDirectory = "{work_dir}"
        if ([System.IO.File]::Exists("{icon_location}")) {{
            $Shortcut.IconLocation = "{icon_location}"
        }}
        $Shortcut.Save()
        """
        # 使用 capture_output=True 可以更好地捕获错误信息
        result = subprocess.run(["powershell", "-Command", ps_command], check=True, capture_output=True, text=True, encoding="utf-8")
        print_color("\n[+] 快捷方式已成功创建到桌面！", Color.OKGREEN)
    except subprocess.CalledProcessError as e:
        print_color("\n[x] 创建快捷方式失败。", Color.FAIL)
        # 打印PowerShell返回的详细错误信息
        print_color("错误详情:", Color.FAIL)
        print_color(e.stderr, Color.FAIL)
    except Exception as e:
        print_color(f"\n[x] 创建快捷方式时发生未知错误: {e}", Color.FAIL)


def main():
    """主函数"""
    print_color("=" * 50, Color.HEADER)
    print_color("  欢迎使用一键式环境部署脚本  ", Color.HEADER)
    print_color("=" * 50, Color.HEADER)
    try:
        input("\n请按 Enter (回车) 键开始部署...")
    except KeyboardInterrupt:
        print_color("\n\n操作已取消。", Color.WARNING)
        sys.exit(0)
    start_time = time.time()
    if not check_runtime_environment():
        print_color("\n部署失败：无法初始化Python运行时。", Color.FAIL)
        sys.exit(1)
    if not install_dependencies():
        print_color("\n部署失败：无法安装项目依赖。", Color.FAIL)
        sys.exit(1)
    create_desktop_shortcut()
    end_time = time.time()
    print_color("\n" + "=" * 50, Color.OKGREEN)
    print_color(f"🎉 全部署流程完成，总耗时: {end_time - start_time:.2f} 秒", Color.OKGREEN)
    print_color("现在你可以通过桌面的快捷方式启动程序了！", Color.OKGREEN)
    print_color("=" * 50, Color.OKGREEN)


if __name__ == "__main__":
    main()
    if platform.system() == "Windows":
        os.system("pause")