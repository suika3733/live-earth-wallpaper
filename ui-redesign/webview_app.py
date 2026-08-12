"""
Live Earth Wallpaper — PyWebView 桌面应用入口
启动 Flask 后端服务，用原生窗口加载 HTML 前端
"""
import sys
import os
import threading
import time
import logging
from pathlib import Path

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import webview

from server import app, run_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("webview_app")

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 51234
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def start_flask():
    """在后台线程启动 Flask"""
    logger.info(f"Starting Flask on {SERVER_URL}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True, use_reloader=False)


def main():
    # 启动 Flask 后台线程
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # 等待 Flask 就绪
    time.sleep(1.0)

    logger.info(f"Opening webview: {SERVER_URL}")

    # 创建原生窗口
    window = webview.create_window(
        title="Live Earth Wallpaper — 卫星壁纸",
        url=SERVER_URL,
        width=1180,
        height=760,
        min_size=(860, 580),
        resizable=True,
        fullscreen=False,
        confirm_close=True,  # 关闭确认
    )

    webview.start(debug=False)

    logger.info("Application closed")


if __name__ == "__main__":
    main()
