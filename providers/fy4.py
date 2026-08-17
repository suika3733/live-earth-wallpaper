"""风云四号 B 星（FY-4B）真彩色全圆盘图获取

数据来源: 国家卫星气象中心（NSMC）公开图片服务 img.nsmc.org.cn
- FY-4B GCLR (AGRI 地理真彩): ~10992x11912 像素，实时更新
- FY-4A MTCC (多通道真彩): ~2198x2198 像素

URL 始终返回最新图，无时间戳 API，通过 Last-Modified 头解析时间戳。
"""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from PIL import Image

from config import IMAGE_CACHE_DIR

logger = logging.getLogger(__name__)

# 关闭 Pillow 大图保护（FY-4B 原图约 1.3 亿像素）
Image.MAX_IMAGE_PIXELS = None

FY4_ENDPOINTS = {
    "fy4b": {
        "name": "FY-4B (风云四号B星)",
        "product": "GCLR 地理真彩",
        "url": "http://img.nsmc.org.cn/CLOUDIMAGE/FY4B/AGRI/GCLR/FY4B_DISK_GCLR.jpg",
    },
    "fy4a": {
        "name": "FY-4A (风云四号A星)",
        "product": "MTCC 多通道真彩",
        "url": "http://img.nsmc.org.cn/CLOUDIMAGE/FY4A/MTCC/FY4A_DISK.jpg",
    },
}

# 分辨率档位（目标长边像素）
FY4_RESOLUTIONS = {
    "standard": {"label": "标准", "size": 2200},
    "hd": {"label": "高清", "size": 4400},
    "uhd": {"label": "超清", "size": 8192},
}

FY4_CACHE_DIR = IMAGE_CACHE_DIR / "fy4"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _fetch_latest(satellite: str = "fy4b", timeout: int = 60) -> tuple[bytes, datetime | None]:
    """下载最新全圆盘图原始字节，返回 (bytes, timestamp)"""
    endpoint = FY4_ENDPOINTS.get(satellite)
    if not endpoint:
        raise ValueError(f"Unknown FY-4 satellite: {satellite}")

    url = endpoint["url"]
    resp = requests.get(url, headers=_HEADERS, timeout=timeout, stream=True)
    resp.raise_for_status()

    data = resp.content

    # 解析 Last-Modified 时间戳
    ts = None
    lm = resp.headers.get("Last-Modified")
    if lm:
        try:
            ts = parsedate_to_datetime(lm).astimezone(timezone.utc)
        except Exception:
            ts = None

    if not data or len(data) < 10_000:
        raise RuntimeError(f"FY-4 响应过小 ({len(data)} bytes)，可能为占位图")

    return data, ts


def fetch_fy4_image(
    satellite: str = "fy4b",
    resolution: str = "hd",
    force: bool = False,
) -> str | None:
    """获取 FY-4 全圆盘图并缩放缓存

    Args:
        satellite: 卫星 (fy4b / fy4a)
        resolution: 分辨率 (standard / hd / uhd)
        force: 强制重新下载

    Returns:
        图像文件路径，失败返回 None
    """
    if satellite not in FY4_ENDPOINTS:
        logger.error(f"Unknown FY-4 satellite: {satellite}")
        return None

    res_info = FY4_RESOLUTIONS.get(resolution, FY4_RESOLUTIONS["hd"])
    target_size = res_info["size"]

    FY4_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = FY4_CACHE_DIR / f"fy4_{satellite}_{resolution}.jpg"

    if not force and cache_path.exists():
        logger.info(f"Using cached FY-4: {cache_path}")
        return str(cache_path)

    logger.info(f"Fetching {satellite} @ {res_info['label']} ({target_size}px)...")
    data, ts = _fetch_latest(satellite)

    from io import BytesIO
    img = Image.open(BytesIO(data))
    img = img.convert("RGB")

    # 缩放（若原图大于目标尺寸）
    max_dim = max(img.width, img.height)
    if max_dim > target_size:
        ratio = target_size / max_dim
        new_w = max(1, int(img.width * ratio))
        new_h = max(1, int(img.height * ratio))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        logger.info(f"Scaled FY-4 to {new_w}x{new_h}")

    img.save(str(cache_path), "JPEG", quality=94)
    logger.info(f"FY-4 saved: {cache_path} ({img.width}x{img.height})")
    return str(cache_path)


def get_fy4_timestamp(satellite: str = "fy4b") -> datetime | None:
    """获取最新图的 Last-Modified 时间戳（仅 HTTP 头，不下载大图）"""
    endpoint = FY4_ENDPOINTS.get(satellite)
    if not endpoint:
        return None
    try:
        resp = requests.head(endpoint["url"], headers=_HEADERS, timeout=15)
        lm = resp.headers.get("Last-Modified")
        if lm:
            return parsedate_to_datetime(lm).astimezone(timezone.utc)
    except Exception:
        pass
    return None
