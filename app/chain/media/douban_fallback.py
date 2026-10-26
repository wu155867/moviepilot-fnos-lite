"""
fnos-lite：豆瓣中文名兜底。

TMDB 识别标题不含中文时（TMDB 中文别名回退已失败），通过豆瓣查询中文译名，
将标题改写为「中文名 原名」格式，供整理命名与 nfo 使用。
供 chain 层各识别路径（按标题 / 按媒体 ID）统一调用。
"""

from typing import Any, Optional, Set

from app.foundation.text import contains_chinese, convert as zhconv_convert
from app.runtime.log import logger
from app.schemas.types import MediaSource

# 豆瓣兜底失败过的媒体标识缓存（进程级，避免重复查询）
_FALLBACK_FAILED: Set[str] = set()


def _cache_key(mediainfo) -> Optional[str]:
    if getattr(mediainfo, "tmdb_id", None):
        return f"tmdb:{mediainfo.tmdb_id}"
    if getattr(mediainfo, "imdb_id", None):
        return f"imdb:{mediainfo.imdb_id}"
    return None


def _applicable(mediainfo) -> bool:
    """
    判断是否需要豆瓣中文名兜底。
    """
    if not mediainfo or getattr(mediainfo, "media_source", None) != MediaSource.TMDB:
        return False
    type_value = getattr(getattr(mediainfo, "type", None), "value", getattr(mediainfo, "type", None))
    if type_value not in ("电影", "电视剧"):
        return False
    key = _cache_key(mediainfo)
    if key and key in _FALLBACK_FAILED:
        return False
    return not contains_chinese(mediainfo.title or "")


def _pick_cn_candidate(result: Any, search_year: Optional[str]) -> Optional[str]:
    """
    从豆瓣搜索结果中挑选年份匹配（±1 年）且标题含中文的条目。
    """
    if not isinstance(result, dict):
        return None
    for item_obj in result.get("items") or []:
        target = item_obj.get("target")
        if not isinstance(target, dict):
            continue
        title = target.get("title")
        if not title or not contains_chinese(str(title)):
            continue
        item_year = str(target.get("year") or "")[:4]
        if search_year and item_year.isdigit() and search_year[:4].isdigit():
            if abs(int(item_year) - int(search_year[:4])) > 1:
                continue
        return str(title)
    return None


def _merge(mediainfo, cn_title: str):
    """
    将中文名合并进媒体信息：标题改为「中文名 原名」。
    """
    cn_title = zhconv_convert(cn_title, "zh-hans").strip()
    original_title = mediainfo.original_title or mediainfo.title or ""
    if not cn_title or not contains_chinese(cn_title) or cn_title in original_title:
        return mediainfo
    mediainfo.title = f"{cn_title} {original_title}".strip()
    names = list(mediainfo.names or [])
    if cn_title not in names:
        names.insert(0, cn_title)
    mediainfo.names = names
    logger.info(f"fnos-lite：已使用豆瓣中文名兜底：{original_title} -> {mediainfo.title}")
    return mediainfo


def _year_match(douban_info: dict, mediainfo) -> bool:
    douban_year = str(douban_info.get("year") or "")[:4]
    year = str(mediainfo.year or "")[:4]
    if not year or not douban_year.isdigit():
        return True
    return abs(int(douban_year) - int(year)) <= 1


def apply_douban_cn_title_fallback(mediainfo):
    """
    豆瓣中文名兜底（同步版）。查询失败或无中文结果时保持原标题。
    """
    if not _applicable(mediainfo):
        return mediainfo
    key = _cache_key(mediainfo)
    search_name = mediainfo.original_title or mediainfo.title
    search_year = str(mediainfo.year) if mediainfo.year else None
    try:
        from app.modules.douban.apiv2 import DoubanApi

        api = DoubanApi()
        merged = mediainfo
        # 第一级：IMDb ID 精确匹配（豆瓣此路径可能返回英文原名）
        if mediainfo.imdb_id:
            info = api.imdbid(mediainfo.imdb_id)
            if isinstance(info, dict) and info.get("title") and _year_match(info, mediainfo):
                merged = _merge(mediainfo, str(info["title"]))
        # 第二级：按名称直接搜索豆瓣
        if merged is mediainfo:
            type_value = getattr(getattr(mediainfo, "type", None), "value", mediainfo.type)
            if type_value == "电视剧":
                result = api.tv_search(search_name, count=10)
            else:
                result = api.movie_search(search_name, count=10)
            cn_title = _pick_cn_candidate(result, search_year)
            if cn_title:
                merged = _merge(mediainfo, cn_title)
    except Exception as e:
        logger.warn(f"fnos-lite：豆瓣中文名兜底查询失败，保持原标题：{e}")
        if key:
            _FALLBACK_FAILED.add(key)
        return mediainfo
    if merged is mediainfo and key:
        _FALLBACK_FAILED.add(key)
    return merged


async def async_apply_douban_cn_title_fallback(mediainfo):
    """
    豆瓣中文名兜底（异步版）。
    """
    if not _applicable(mediainfo):
        return mediainfo
    key = _cache_key(mediainfo)
    search_name = mediainfo.original_title or mediainfo.title
    search_year = str(mediainfo.year) if mediainfo.year else None
    try:
        from app.modules.douban.apiv2 import DoubanApi

        api = DoubanApi()
        merged = mediainfo
        # 第一级：IMDb ID 精确匹配（豆瓣此路径可能返回英文原名）
        if mediainfo.imdb_id:
            info = await api.async_imdbid(mediainfo.imdb_id)
            if isinstance(info, dict) and info.get("title") and _year_match(info, mediainfo):
                merged = _merge(mediainfo, str(info["title"]))
        # 第二级：按名称直接搜索豆瓣
        if merged is mediainfo:
            type_value = getattr(getattr(mediainfo, "type", None), "value", mediainfo.type)
            if type_value == "电视剧":
                result = await api.async_tv_search(search_name, count=10)
            else:
                result = await api.async_movie_search(search_name, count=10)
            cn_title = _pick_cn_candidate(result, search_year)
            if cn_title:
                merged = _merge(mediainfo, cn_title)
    except Exception as e:
        logger.warn(f"fnos-lite：豆瓣中文名兜底查询失败，保持原标题：{e}")
        if key:
            _FALLBACK_FAILED.add(key)
        return mediainfo
    if merged is mediainfo and key:
        _FALLBACK_FAILED.add(key)
    return merged
