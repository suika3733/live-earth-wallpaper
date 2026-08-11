"""调度模块 - 支持 NASA APOD 每日 + Himawari-8 每小时更新"""
import threading
import logging
from datetime import datetime, timedelta

from config import load_config, save_config, load_metadata, save_metadata
from nasa_api import fetch_apod, download_image
from categorizer import categorize_image
from wallpaper import set_wallpaper, watermark_image

logger = logging.getLogger(__name__)

_scheduler_thread = None
_stop_event = threading.Event()
_last_earth_tick = None  # Himawari-8 上次更新时间


def check_and_update() -> bool:
    """NASA APOD 每日检查更新"""
    config = load_config()
    selected_category = config.get("selected_category", "all")

    logger.info(f"Daily update check, category: {selected_category}")

    image = fetch_apod(api_key=config.get("api_key"))
    if not image:
        logger.warning("Today APOD fetch failed")
        return False

    cat = categorize_image(image)
    logger.info(f"Today APOD: {cat} - {image.title}")

    metadata = load_metadata()
    metadata["images"][image.date] = image.to_dict()
    save_metadata(metadata)

    if selected_category != "all" and cat != selected_category:
        logger.info(f"Category mismatch: {cat} vs {selected_category}, skip")
        download_image(image)
        return False

    path = download_image(image)
    if not path:
        logger.warning("Image download failed")
        return False

    style = config.get("wallpaper_style", "fill")
    wp_path = watermark_image(
        path,
        left_text="来源: NASA 每日天文图片 (APOD)",
        right_text=f"拍摄: {image.date} | {image.title}",
        output_key=f"apod_{image.date}",
    )
    if set_wallpaper(wp_path, image.date.replace("-", ""), style=style):
        config["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_config(config)
        logger.info("Wallpaper updated")
        return True

    return False


def check_and_update_earth() -> bool:
    """Himawari-8 实时地球更新（2200x2200 高清）"""
    from earth_api import fetch_earth_image

    config = load_config()
    style = config.get("wallpaper_style", "fill")

    logger.info("Earth update check @ 2200x2200")
    path = fetch_earth_image(resolution=2200)
    if not path:
        logger.warning("Earth image download failed")
        return False

    now = datetime.now()
    wp_path = watermark_image(
        path,
        left_text="来源: Himawari-8 气象卫星",
        right_text=f"拍摄时间: {now.strftime('%Y-%m-%d %H:%M')} (UTC+8)",
        output_key="earth_live",
    )
    if set_wallpaper(wp_path, "earth_live", style=style):
        config["last_earth_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_config(config)
        logger.info("Earth wallpaper updated")
        return True

    return False


def _scheduler_loop():
    global _last_earth_tick
    logger.info("Scheduler started")

    while not _stop_event.is_set():
        try:
            config = load_config()
            data_source = config.get("data_source", "apod")

            if data_source == "earth":
                # Himawari-8: 每 10 分钟检查一次（匹配卫星拍摄频率）
                now = datetime.now()
                minute_key = now.strftime("%Y-%m-%d %H:%M")
                minute_key_10 = now.strftime("%Y-%m-%d %H:") + str((now.minute // 10) * 10).zfill(2)

                if not config.get("auto_update", True):
                    _stop_event.wait(300)
                    continue

                if _last_earth_tick != minute_key_10:
                    check_and_update_earth()
                    _last_earth_tick = minute_key_10

                _stop_event.wait(300)  # 每 5 分钟检查一次
            else:
                # NASA APOD: 每天检查一次
                if not config.get("auto_update", True):
                    _stop_event.wait(300)
                    continue

                today = datetime.now().strftime("%Y-%m-%d")
                last_update = config.get("last_update", "")
                if last_update.startswith(today):
                    update_time = config.get("update_time", "09:00")
                    tomorrow = datetime.now() + timedelta(days=1)
                    try:
                        next_run = datetime.strptime(
                            f"{tomorrow.strftime('%Y-%m-%d')} {update_time}",
                            "%Y-%m-%d %H:%M"
                        )
                        wait_seconds = (next_run - datetime.now()).total_seconds()
                        wait_seconds = max(60, min(wait_seconds, 86400))
                    except ValueError:
                        wait_seconds = 3600

                    logger.info(f"Already updated today, wait {wait_seconds:.0f}s")
                    _stop_event.wait(wait_seconds)
                    continue

                check_and_update()
                _stop_event.wait(3600)

        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            _stop_event.wait(1800)

    logger.info("Scheduler stopped")


def start_scheduler():
    global _scheduler_thread, _stop_event

    if _scheduler_thread and _scheduler_thread.is_alive():
        logger.info("Scheduler already running")
        return

    _stop_event = threading.Event()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Scheduler thread started")


def stop_scheduler():
    global _stop_event
    if _stop_event:
        _stop_event.set()
    logger.info("Scheduler stop signal sent")


def is_scheduler_running() -> bool:
    return _scheduler_thread is not None and _scheduler_thread.is_alive()
