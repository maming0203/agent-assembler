"""Sidecar 基类与总线——插件加载、卸载、调度的核心。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class SidecarBase(ABC):
    """所有 Sidecar 插件的基类。"""

    name: str = "base"
    version: str = "0.1.0"

    @abstractmethod
    def pre_process(self, query: str) -> str:
        """查询前处理。"""
        pass

    @abstractmethod
    def post_process(self, result: dict) -> dict:
        """结果后处理。"""
        pass

    def meta(self) -> dict:
        """返回插件元信息。"""
        return {"name": self.name, "version": self.version}


class SidecarBus:
    """Sidecar 总线——管理插件的加载、卸载、调度。"""

    def __init__(self):
        self._sidecars: dict[str, SidecarBase] = {}

    def register(self, sidecar: SidecarBase):
        """注册一个 Sidecar 插件。"""
        self._sidecars[sidecar.name] = sidecar

    def unregister(self, name: str):
        """卸载一个 Sidecar 插件。"""
        self._sidecars.pop(name, None)

    def get(self, name: str) -> Optional[SidecarBase]:
        """获取指定名称的 Sidecar。"""
        return self._sidecars.get(name)

    def list_sidecars(self) -> list[dict]:
        """列出所有已注册的 Sidecar 元信息。"""
        return [s.meta() for s in self._sidecars.values()]

    def pre_process_all(self, query: str) -> str:
        """对所有 Sidecar 执行 pre_process 链。"""
        for s in self._sidecars.values():
            query = s.pre_process(query)
        return query

    def post_process_all(self, result: dict) -> dict:
        """对所有 Sidecar 执行 post_process 链。"""
        for s in self._sidecars.values():
            result = s.post_process(result)
        return result
