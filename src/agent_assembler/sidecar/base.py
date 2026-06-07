"""Sidecar Bus — 插件热插拔总线"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# ──────────────────────────────────────────
# Sidecar 基类
# ──────────────────────────────────────────

class SidecarBase(ABC):
    """所有 Sidecar 插件的基类。
    
    Sidecar 是 Agent Assembler 的插件机制——
    通过标准接口（pre_process / post_process）实现能力的热插拔。
    """
    name: str = "base"
    version: str = "0.1.0"
    
    @abstractmethod
    def pre_process(self, query: str) -> str:
        """查询前处理。可对用户输入做增强、过滤、转换。"""
        pass
    
    @abstractmethod
    def post_process(self, result: dict) -> dict:
        """结果后处理。可对输出做判定、格式化、持久化。"""
        pass
    
    def meta(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


# ──────────────────────────────────────────
# SidecarBus: 总线
# ──────────────────────────────────────────

class SidecarBus:
    """Sidecar 总线——管理插件的注册、卸载、调度。
    
    用法：
        bus = SidecarBus()
        bus.register(DecisionEngine())
        bus.register(Simulator())
        query = bus.pre_process_all(user_query)
        result = llm_call(query)
        result = bus.post_process_all(result)
    """
    
    def __init__(self):
        self._sidecars: dict[str, SidecarBase] = {}
    
    def register(self, sidecar: SidecarBase):
        """注册 Sidecar 插件"""
        if not isinstance(sidecar, SidecarBase):
            raise TypeError(f"sidecar must be a SidecarBase subclass, got {type(sidecar).__name__}")
        self._sidecars[sidecar.name] = sidecar
    
    def unregister(self, name: str):
        """卸载 Sidecar 插件"""
        self._sidecars.pop(name, None)
    
    def get(self, name: str) -> SidecarBase | None:
        return self._sidecars.get(name)
    
    def list_sidecars(self) -> list[dict[str, str]]:
        return [s.meta() for s in self._sidecars.values()]
    
    def pre_process_all(self, query: str) -> str:
        """依次调用所有 Sidecar 的 pre_process"""
        for sidecar in self._sidecars.values():
            query = sidecar.pre_process(query)
        return query
    
    def post_process_all(self, result: dict) -> dict:
        """依次调用所有 Sidecar 的 post_process"""
        for sidecar in self._sidecars.values():
            result = sidecar.post_process(result)
        return result
    
    def __len__(self) -> int:
        return len(self._sidecars)
    
    def __repr__(self) -> str:
        names = ", ".join(self._sidecars.keys())
        return f"SidecarBus([{names}])"
