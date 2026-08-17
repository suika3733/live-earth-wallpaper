"""卫星数据源提供器 - 支持多颗地球静止卫星 + FY-4 + SDO 太阳观测"""
from .geostationary import (
    GEOSTATIONARY_SATELLITES,
    SATELLITE_SIZES,
    fetch_satellite_image,
)
from .sdo import SDO_BANDS, fetch_sdo_image
from .fy4 import FY4_ENDPOINTS, FY4_RESOLUTIONS, fetch_fy4_image

__all__ = [
    "GEOSTATIONARY_SATELLITES",
    "SATELLITE_SIZES",
    "SDO_BANDS",
    "FY4_ENDPOINTS",
    "FY4_RESOLUTIONS",
    "fetch_satellite_image",
    "fetch_sdo_image",
    "fetch_fy4_image",
]
