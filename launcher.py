"""
RealEarth 真实地球 — 4.0.0 入口
单进程 Tkinter 桌面应用（不再依赖 Web UI / WebView2）。

架构说明（对比旧版 Web UI 的优势）：
- 旧版 Web UI 采用 "Flask 后端 + pywebview/Edge WebView2 前端" 三层结构，
  调度器长阻塞 wait 导致配置无法实时生效，且 ExitProcess 会残留 msedgewebview2
  子进程，表现为「无法关闭软件」。
- 4.0.0 回归 Tkinter 单进程模型：应用直接掌控主循环、调度器与关闭流程，
  退出干净，自动刷新/自动壁纸实时生效。
"""
import sys
import os
import socket
import logging
from pathlib import Path

# ---- 路径设置 ----
FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    MEIPASS = Path(sys._MEIPASS)
    BASE_DIR = MEIPASS
else:
    BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

from logging.handlers import RotatingFileHandler

# 日志目录
_LOG_DIR = Path.home() / ".nasa_wallpaper" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "app.log"

# 根日志器配置（同时输出到文件和控制台）
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.handlers.clear()

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_fh = RotatingFileHandler(str(_LOG_FILE), maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8")
_fh.setFormatter(_fmt)
_root_logger.addHandler(_fh)

_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)
_root_logger.addHandler(_ch)

logger = logging.getLogger("launcher")

# 单实例锁定端口（仅本机回环，无实际服务）
LOCK_HOST = "127.0.0.1"
LOCK_PORT = 51123


def _acquire_single_instance() -> bool:
    """尝试占用回环端口作为单实例锁。成功返回 True，已被占用返回 False。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        sock.bind((LOCK_HOST, LOCK_PORT))
        sock.listen(1)
        # 保存引用，避免被 GC 关闭端口
        _acquire_single_instance._sock = sock
        return True
    except OSError:
        return False


def main():
    # 单实例保护
    if not _acquire_single_instance():
        logger.warning("检测到已有实例运行，本实例退出")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "RealEarth 已在运行。\n请在系统托盘（右下角）找到 Earth 图标。",
                "已在运行",
                0x40,  # MB_ICONINFORMATION
            )
        except Exception:
            pass
        return

    logger.info("Starting RealEarth 4.0.0 (Tkinter single-process)...")

    # 直接启动 Tkinter 应用；调度器、托盘、关闭流程均由 main.ui 内部接管
    import main as app_module
    app_module.main()

    logger.info("RealEarth 已退出")


if __name__ == "__main__":
    main()
