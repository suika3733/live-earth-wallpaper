"""
Live Earth Wallpaper — 新版 Web UI 入口
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("launcher")

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 51234
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

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


def _create_tray_image():
    from PIL import Image, ImageDraw

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
        "LiveEarthWallpaper",
        _create_tray_image(),
        "Live Earth Wallpaper",
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

    # 启动 Flask
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    time.sleep(1.0)
    logger.info(f"Server ready: {SERVER_URL}")

    # 尝试 WebView，失败则打开浏览器
    try:
        import webview

        api = WindowAPI()

        _window = webview.create_window(
            title="Live Earth Wallpaper — 卫星壁纸",
            url=SERVER_URL,
            width=1180,
            height=760,
            min_size=(860, 580),
            resizable=True,
            frameless=True,
            easy_drag=False,
            confirm_close=False,
            js_api=api,
        )

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
