"""NASA APOD API 客户端"""
import logging
import os
import requests
from dataclasses import dataclass
from datetime import datetime, timedelta

from config import APOD_API_URL, get_image_cache_path

logger = logging.getLogger(__name__)


@dataclass
class ApodImage:
    date: str
    title: str
    explanation: str
    media_type: str
    url: str
    hdurl: str | None = None
    copyright: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ApodImage":
        return cls(
            date=data.get("date", ""),
            title=data.get("title", ""),
            explanation=data.get("explanation", ""),
            media_type=data.get("media_type", ""),
            url=data.get("url", ""),
            hdurl=data.get("hdurl"),
            copyright=data.get("copyright"),
        )

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "title": self.title,
            "explanation": self.explanation,
            "media_type": self.media_type,
            "url": self.url,
            "hdurl": self.hdurl,
            "copyright": self.copyright,
        }


def fetch_apod(api_key: str = None, date: str = None) -> ApodImage | None:
    if not api_key:
        from config import DEFAULT_API_KEY
        api_key = DEFAULT_API_KEY

    params = {"api_key": api_key}
    if date:
        params["date"] = date

    try:
        resp = requests.get(APOD_API_URL, params=params, timeout=15)
        if resp.status_code == 200:
            return ApodImage.from_dict(resp.json())
        logger.warning(f"APOD API {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"APOD fetch error: {e}")
    return None


def fetch_apod_range(start_date: str, end_date: str = None, api_key: str = None) -> list[ApodImage]:
    if not api_key:
        from config import DEFAULT_API_KEY
        api_key = DEFAULT_API_KEY

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    params = {"api_key": api_key, "start_date": start_date, "end_date": end_date}

    try:
        resp = requests.get(APOD_API_URL, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            images = [ApodImage.from_dict(item) for item in data if item.get("media_type") == "image"]
            return images
        logger.warning(f"APOD range API {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"APOD range fetch error: {e}")
    return []


def download_image(image: ApodImage, hd: bool = True) -> str | None:
    url = image.hdurl if (hd and image.hdurl) else image.url
    if not url:
        logger.warning(f"No URL for {image.date}")
        return None

    cache_path = get_image_cache_path(image.date, hd=hd)
    if cache_path.exists():
        return str(cache_path)

    try:
        resp = requests.get(url, timeout=60, stream=True)
        if resp.status_code == 200:
            with open(cache_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(cache_path)
        logger.warning(f"Download {resp.status_code} for {url}")
    except Exception as e:
        logger.error(f"Download error: {e}")
    return None
