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
    # PyInstaller 打包后：所有 .py 扁平化，HTML 在 MEIPASS 根目录
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


def start_flask():
    flask_server.app.run(
        host=SERVER_HOST, port=SERVER_PORT,
        debug=False, threaded=True, use_reloader=False
    )


def main():
    # 启动 Flask
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    time.sleep(1.0)
    logger.info(f"Server ready: {SERVER_URL}")

    # 尝试 WebView，失败则打开浏览器
    try:
        import webview
        logger.info("Starting pywebview window...")
        window = webview.create_window(
            title="Live Earth Wallpaper — 卫星壁纸",
            url=SERVER_URL,
            width=1180, height=760,
            min_size=(860, 580),
            resizable=True,
            confirm_close=True,
        )
        webview.start(debug=False)
    except Exception:
        logger.info("pywebview unavailable, opening browser...")
        import webbrowser
        try:
            webbrowser.open(SERVER_URL)
        except Exception:
            logger.info(f"Please open {SERVER_URL} manually")
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    logger.info("Shutting down")


if __name__ == "__main__":
    main()
