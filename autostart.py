"""开机自启动管理 — Windows 注册表方式"""
import logging
import sys
import winreg
from pathlib import Path

logger = logging.getLogger(__name__)

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "LivingEarthWallpaper"


def _get_startup_command() -> str:
    """获取自启动命令

    打包后的 exe: 直接指向 exe 路径
    脚本模式: pythonw.exe + 脚本路径
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后的 exe
        return f'"{sys.executable}"'
    else:
        # 开发模式：pythonw + 脚本
        python_exe = sys.executable
        # 用 pythonw.exe 避免弹出控制台窗口
        pythonw = str(Path(python_exe).parent / "pythonw.exe")
        if Path(pythonw).exists():
            python_exe = pythonw
        script = str(Path(sys.argv[0]).resolve())
        return f'"{python_exe}" "{script}"'


def is_autostart_enabled() -> bool:
    """检查是否已设置开机自启动"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.warning(f"Check autostart failed: {e}")
        return False


def enable_autostart() -> bool:
    """启用开机自启动"""
    try:
        command = _get_startup_command()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        logger.info(f"Autostart enabled: {command}")
        return True
    except Exception as e:
        logger.error(f"Enable autostart failed: {e}")
        return False


def disable_autostart() -> bool:
    """禁用开机自启动"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        logger.info("Autostart disabled")
        return True
    except FileNotFoundError:
        # 本来就没有，视为成功
        return True
    except Exception as e:
        logger.error(f"Disable autostart failed: {e}")
        return False


def set_autostart(enabled: bool) -> bool:
    """设置开机自启动状态"""
    if enabled:
        return enable_autostart()
    else:
        return disable_autostart()
