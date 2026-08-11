"""图片分类逻辑"""
import logging
from config import CATEGORIES

logger = logging.getLogger(__name__)


def categorize_image(image) -> str:
    text = f"{image.title} {image.explanation}".lower()
    scores = {}

    for key, info in CATEGORIES.items():
        score = 0
        for kw in info["keywords"]:
            if kw.lower() in text:
                score += 1
                if kw.lower() in image.title.lower():
                    score += 2
        if score > 0:
            scores[key] = score

    if not scores:
        return "other"
    return max(scores, key=scores.get)


def get_category_name(key: str) -> str:
    if key == "all":
        return "全部"
    if key == "other":
        return "其他"
    return CATEGORIES.get(key, {}).get("name", key)


def get_all_category_keys() -> list[str]:
    return ["all"] + list(CATEGORIES.keys()) + ["other"]
