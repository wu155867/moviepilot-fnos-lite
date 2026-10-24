"""
站点认证与索引资源的空实现（fnos-lite）。

本版本移除了 PT 站点功能，原闭源 Cython 扩展不再拉取；
此模块提供接口兼容的空实现，保证宿主导入与启动不受影响。
"""

from typing import Any, List, Optional, Tuple


class SitesHelper:
    """
    站点助手的空实现，所有站点能力返回不可用。
    """

    def __init__(self) -> None:
        pass

    @property
    def auth_version(self) -> str:
        return ""

    @property
    def indexer_version(self) -> str:
        return ""

    @property
    def auth_level(self) -> int:
        return 0

    def check(self, domain: str) -> Tuple[bool, str]:
        return False, "站点功能已在本版本中移除"

    def get_indexers(self) -> List[dict[str, Any]]:
        return []

    async def async_get_indexers(self) -> List[dict[str, Any]]:
        return []

    def get_indexer(self, domain: str) -> Optional[dict[str, Any]]:
        return None

    async def async_get_indexer(self, domain: str) -> Optional[dict[str, Any]]:
        return None

    def get_authsites(self) -> dict[str, Any]:
        return {}

    def get_indexsites(self) -> dict[str, Any]:
        return {}

    def check_user(
        self,
        site: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        return False, "站点功能已在本版本中移除"
