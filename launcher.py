"""
RealEarth 真实地球 — 新版 Web UI 入口
支持 PyInstaller 打包，Flask 后端 + WebView/Browser 前端
"""
import sys
import os
import threading
import time
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

# ---- 导入 ui-redesign/server.py ----
_ui_dir = BASE_DIR / "ui-redesign"
if _ui_dir.exists():
    sys.path.insert(0, str(_ui_dir))

import server as flask_server

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

# 文件处理器（最多保留 5 个文件，每个最大 2MB）
_fh = RotatingFileHandler(str(_LOG_FILE), maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8")
_fh.setFormatter(_fmt)
_root_logger.addHandler(_fh)

# 控制台处理器
_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)
_root_logger.addHandler(_ch)

logger = logging.getLogger("launcher")

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 51234
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def _is_already_running() -> bool:
    """检测是否已有实例在运行（端口被占用即视为已运行）"""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        result = s.connect_ex((SERVER_HOST, SERVER_PORT))
        return result == 0
    finally:
        s.close()


# ---- 系统托盘 & 窗口状态 ----
_tray_icon = None
_window = None
_window_maximized = False


class WindowAPI:
    """暴露给前端 JS 的 API"""

    def hide(self):
        if _window:
            _window.hide()
        return True

    def show(self):
        if _window:
            _window.show()
            _window.restore()
        return True

    def minimize(self):
        if _window:
            _window.minimize()
        return True

    def toggle_maximize(self):
        global _window_maximized
        if _window:
            if _window_maximized:
                _window.restore()
            else:
                _window.maximize()
        return True

    def quit_app(self):
        if _tray_icon:
            _tray_icon.stop()
        if _window:
            _window.destroy()
        return True


def _get_logo_path():
    """查找 logo 图片路径（打包/开发两种模式）"""
    candidates = [
        BASE_DIR / "logo.png",                   # FROZEN: MEIPASS/logo.png
        BASE_DIR / "ui-redesign" / "logo.png",  # 开发: ui-redesign/logo.png
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _get_ico_path():
    """查找 ico 图标路径（用于窗口/任务栏图标）"""
    candidates = [
        BASE_DIR / "logo.ico",                   # FROZEN: MEIPASS/logo.ico
        BASE_DIR / "ui-redesign" / "logo.ico",  # 开发: ui-redesign/logo.ico
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _create_tray_image():
    from PIL import Image, ImageDraw

    # 优先使用新 logo
    logo_path = _get_logo_path()
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            return logo.resize((64, 64), Image.LANCZOS)
        except Exception as e:
            logger.warning(f"Load tray logo failed: {e}")

    # 回退：代码绘制的圆形图标
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(img)
    dc.ellipse([4, 4, 60, 60], fill=(77, 171, 154))
    dc.ellipse([14, 14, 50, 50], fill=(26, 90, 138))
    dc.ellipse([20, 16, 36, 28], fill=(255, 255, 255, 60))
    return img


def _on_tray_show(icon, item):
    if _window:
        _window.show()
        _window.restore()


def _on_tray_quit(icon, item):
    if _window:
        _window.destroy()
    icon.stop()


def _run_tray():
    global _tray_icon
    import pystray

    menu = pystray.Menu(
        pystray.MenuItem("显示窗口", _on_tray_show),
        pystray.MenuItem("退出", _on_tray_quit),
    )
    _tray_icon = pystray.Icon(
        "RealEarth",
        _create_tray_image(),
        "RealEarth 真实地球",
        menu,
    )
    _tray_icon.run()


def _on_window_maximized():
    global _window_maximized
    _window_maximized = True


def _on_window_restored():
    global _window_maximized
    _window_maximized = False


def _on_window_closing():
    # 阻止关闭，改为隐藏到托盘
    if _window:
        _window.hide()
    return False


def start_flask():
    flask_server.app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


def main():
    global _window

    # 单实例保护：已有实例运行时，直接退出，避免端口冲突导致界面错乱
    if _is_already_running():
        logger.warning("检测到已有实例运行，本实例退出")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "RealEarth 已在运行。\n请检查系统托盘图标（右下角）。",
                "已在运行",
                0x40,  # MB_ICONINFORMATION
            )
        except Exception:
            pass
        return

    # 启动 Flask
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    time.sleep(1.0)
    logger.info(f"Server ready: {SERVER_URL}")

    # 尝试 WebView，失败则打开浏览器
    try:
        import webview

        api = WindowAPI()

        _icon_path = _get_ico_path()
        _window_kwargs = dict(
            title="RealEarth — 真实地球",
            url=SERVER_URL,
            width=1280,
            height=800,
            min_size=(1000, 640),
            resizable=True,
            frameless=True,
            easy_drag=False,
            confirm_close=False,
            js_api=api,
        )
        if _icon_path:
            _window_kwargs["icon"] = _icon_path

        _window = webview.create_window(**_window_kwargs)

        _window.events.closing += _on_window_closing
        _window.events.maximized += _on_window_maximized
        _window.events.restored += _on_window_restored

        # 启动系统托盘（后台线程）
        tray_thread = threading.Thread(target=_run_tray, daemon=True)
        tray_thread.start()

        logger.info("Starting pywebview window (frameless)...")
        webview.start(debug=False)
    except Exception:
        logger.info("pywebview unavailable, opening browser...")
        import webbrowser

        try:
            webbrowser.open(SERVER_URL)
        except Exception:
            logger.info(f"Please open {SERVER_URL} manually")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # 退出时停止托盘
    if _tray_icon:
        _tray_icon.stop()

    logger.info("Shutting down")


if __name__ == "__main__":
    main()
