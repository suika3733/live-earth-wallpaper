"""Himawari-8 实时地球卫星图数据源

日本 Himawari-8 气象卫星每 10 分钟拍摄一张地球全盘图。
数据延迟约 20-30 分钟，D531106 公开产品提供多级分辨率。

来源: https://himawari8.nict.go.jp/

分辨率级别 (D531106):
  1d  = 1x1  tiles =    550x550   (最低，1张)
  4d  = 4x4  tiles =  2,200x2,200 (推荐，16张)
  8d  = 8x8  tiles =  4,400x4,400 (超清，64张)
  16d = 16x16 tiles = 8,800x8,800 (极清，256张)
  20d = 20x20 tiles = 11,000x11,000 (最高，400张)
"""
import logging
import io
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

from config import IMAGE_CACHE_DIR

logger = logging.getLogger(__name__)

BASE_URL = "https://himawari8.nict.go.jp/img/D531106"
TILE_SIZE = 550
LATEST_IMAGE_FILE = IMAGE_CACHE_DIR / "earth_latest.png"

# 分辨率配置: (grid_size, name, tile_count)
RESOLUTIONS = {
    550:  (1,  "550x550"),
    1100: (2,  "1100x1100"),   # 通过 4d 下载后缩放
    2200: (4,  "2200x2200"),   # 推荐：4d = 4x4 瓦片
    4400: (8,  "4400x4400"),
}


def _get_latest_time_slot() -> str:
    """获取最新可用时间片（UTC 减 30 分钟延迟，取整到 10 分钟）"""
    now = datetime.utcnow()
    now -= timedelta(minutes=30)
    minute = (now.minute // 10) * 10
    now = now.replace(minute=minute, second=0, microsecond=0)
    return now.strftime("%Y/%m/%d/%H%M%S")


def _download_tile(time_slot: str, grid_size: int, row: int, col: int) -> tuple[int, int, Image.Image | None]:
    """下载单个瓦片，返回 (row, col, image_or_None)"""
    url = f"{BASE_URL}/{grid_size}d/550/{time_slot}_{col}_{row}.png"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return (row, col, Image.open(io.BytesIO(resp.content)))
        else:
            logger.debug(f"Tile missing ({resp.status_code}): row={row},col={col}")
    except Exception as e:
        logger.debug(f"Tile error row={row},col={col}: {type(e).__name__}")
    return (row, col, None)


def _stitch_tiles(time_slot: str, grid_size: int, max_workers: int = 8) -> Image.Image | None:
    """并行下载并拼接瓦片为完整图

    Args:
        time_slot: 时间片字符串，如 "2026/08/11/050000"
        grid_size: 每边瓦片数，4d=4, 8d=8, 16d=16
        max_workers: 并行下载线程数

    Returns:
        拼接后的 PIL Image，失败返回 None
    """
    total_tiles = grid_size * grid_size
    logger.info(f"Downloading {grid_size}x{grid_size} ({total_tiles} tiles) for {time_slot}")

    # 并行下载所有瓦片
    tiles = [[None] * grid_size for _ in range(grid_size)]
    success_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_download_tile, time_slot, grid_size, row, col): (row, col)
            for row in range(grid_size) for col in range(grid_size)
        }

        for future in as_completed(futures):
            row, col, img = future.result()
            if img is not None:
                tiles[row][col] = img
                success_count += 1

    logger.info(f"Downloaded {success_count}/{total_tiles} tiles")

    if success_count == 0:
        return None

    # 拼接
    full_w = TILE_SIZE * grid_size
    full_h = TILE_SIZE * grid_size
    full = Image.new("RGB", (full_w, full_h))

    for row in range(grid_size):
        for col in range(grid_size):
            tile = tiles[row][col]
            if tile:
                full.paste(tile, (col * TILE_SIZE, row * TILE_SIZE))
            else:
                # 用已下载的相邻瓦片填充缺失位置
                for dr, dc in [(-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (-1, 1)]:
                    nr, nc = row + dr, col + dc
                    if 0 <= nr < grid_size and 0 <= nc < grid_size and tiles[nr][nc]:
                        full.paste(tiles[nr][nc], (col * TILE_SIZE, row * TILE_SIZE))
                        break

    return full


def fetch_earth_image(cache_path: str = None, resolution: int = 2200) -> str | None:
    """获取最新 Himawari-8 地球全盘图

    尝试最近 3 个时间片，找到第一个可用的拼接为完整图。

    Args:
        cache_path: 缓存路径，默认 IMAGE_CACHE_DIR / earth_latest.png
        resolution: 目标分辨率: 550 | 1100 | 2200 | 4400

    Returns:
        保存路径，失败返回 None
    """
    if cache_path is None:
        cache_path = str(LATEST_IMAGE_FILE)

    # 确定网格大小
    res_info = RESOLUTIONS.get(resolution)
    if not res_info:
        logger.warning(f"Unknown resolution {resolution}, fallback to 2200")
        grid_size, name = 4, "2200x2200"
    else:
        grid_size, name = res_info

    # 1100 特殊处理：下载 4d 后缩放到 1/2
    scale_to_half = (resolution == 1100)

    base_time = _get_latest_time_slot()
    base_dt = datetime.strptime(base_time, "%Y/%m/%d/%H%M%S")

    logger.info(f"Fetching Himawari-8 @ {name} (grid={grid_size}d)")

    for offset in range(3):
        dt = base_dt - timedelta(minutes=offset * 10)
        time_slot = dt.strftime("%Y/%m/%d/%H%M%S")

        if grid_size <= 1:
            # 550 分辨率：直接下载单瓦片
            url = f"{BASE_URL}/1d/550/{time_slot}_0_0.png"
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content))
                    img.save(cache_path, "PNG")
                    logger.info(f"Earth image saved: {cache_path} ({img.size})")
                    return cache_path
            except Exception as e:
                logger.error(f"550 download error: {type(e).__name__}: {e}")
        else:
            # 拼接多瓦片
            img = _stitch_tiles(time_slot, grid_size)
            if img:
                if scale_to_half:
                    # 1100: 4d (2200) 缩放到 1/2
                    half_w, half_h = img.width // 2, img.height // 2
                    img = img.resize((half_w, half_h), Image.LANCZOS)
                    logger.info(f"Scaled to {half_w}x{half_h} for 1100")

                img.save(cache_path, "PNG")
                logger.info(f"Earth image saved: {cache_path} ({img.size})")
                return cache_path
            else:
                logger.debug(f"Time slot {time_slot} failed, trying earlier...")

    logger.warning("All time slots failed")
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = fetch_earth_image(resolution=2200)
    if path:
        img = Image.open(path)
        print(f"OK: {path} ({img.size})")
    else:
        print("FAILED")
