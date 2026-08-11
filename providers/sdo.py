"""NASA SDO 太阳动力学天文台 - 太阳实时图像

数据来源: https://sdo.gsfc.nasa.gov
支持波段: 0171, 0304, HMIIC 等
"""

import bisect
import logging
from pathlib import Path

from PIL import Image
from io import BytesIO
import requests

from config import IMAGE_CACHE_DIR

logger = logging.getLogger(__name__)

SDO_RESOLUTIONS = [512, 1024, 2048, 4096]

SDO_BANDS = {
    "0304":      {"name": "304 Å (色球层)",     "desc": "极紫外 - 太阳色球层与过渡区"},
    "0171":      {"name": "171 Å (日冕)",       "desc": "极紫外 - 太阳日冕"},
    "0304pfss":  {"name": "304 Å + PFSS",     "desc": "304 埃 + 磁场线叠加"},
    "0171pfss":  {"name": "171 Å + PFSS",     "desc": "171 埃 + 磁场线叠加"},
    "HMIIC":     {"name": "连续光球 (可见光)",  "desc": "可见光 - 太阳黑子与表面"},
}

SDO_CACHE_DIR = IMAGE_CACHE_DIR / "sdo"


def _pick_resolution(target: int) -> int:
    """选择不小于 target 的最小可用分辨率"""
    return SDO_RESOLUTIONS[bisect.bisect_left(SDO_RESOLUTIONS, target)]


def fetch_sdo_image(
    band: str = "0304",
    target_size: int = 1024,
    force: bool = False,
) -> str | None:
    """获取 NASA SDO 太阳最新图像

    Args:
        band: 波段 (0304 / 0171 / 0304pfss / 0171pfss / HMIIC)
        target_size: 目标尺寸，自动选择 512/1024/2048/4096 中最接近的
        force: 强制重新下载

    Returns:
        图像文件路径，失败返回 None
    """
    if band not in SDO_BANDS:
        logger.error(f"Unknown SDO band: {band}")
        return None

    resolution = _pick_resolution(target_size)

    SDO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = SDO_CACHE_DIR / f"sdo_{band}_{resolution}.jpg"

    if not force and cache_path.exists():
        logger.info(f"Using cached SDO: {cache_path}")
        return str(cache_path)

    url = f"https://sdo.gsfc.nasa.gov/assets/img/latest/latest_{resolution}_{band}.jpg"
    logger.info(f"Fetching SDO: {url}")

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))
        img.save(str(cache_path), "JPEG", quality=94)
        logger.info(f"SDO saved: {cache_path} ({img.width}x{img.height})")
        return str(cache_path)
    except Exception as e:
        logger.error(f"SDO download failed: {e}")
        return None
