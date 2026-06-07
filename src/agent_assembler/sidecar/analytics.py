"""Analytics — 数据分析（数据持久化、可视化管道）"""
from __future__ import annotations

from .base import SidecarBase


class Analytics(SidecarBase):
    """数据分析——查询追踪、指标收集、可视化管道。
    
    当前为骨架，后续接入数据库持久化、图表生成。
    """
    name = "analytics"
    version = "0.1.0"
    
    def __init__(self):
        self._metrics: list[dict[str, str]] = []
    
    def pre_process(self, query: str) -> str:
        return query
    
    def post_process(self, result: dict) -> dict:
        self._metrics.append({
            "query": result.get("query", ""),
            "agent": result.get("agent", ""),
        })
        result["analytics_tracked"] = True
        return result
    
    @property
    def metrics(self) -> list[dict[str, str]]:
        return self._metrics.copy()
    
    def clear_metrics(self):
        self._metrics.clear()
