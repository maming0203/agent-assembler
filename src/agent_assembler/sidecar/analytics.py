"""Analytics Sidecar——数据持久化和可视化管道。"""

from .base import SidecarBase


class Analytics(SidecarBase):
    """数据分析——数据持久化和可视化管道。"""

    name = "analytics"

    def __init__(self):
        self._metrics = []

    def pre_process(self, query: str) -> str:
        """查询前处理。"""
        return query

    def post_process(self, result: dict) -> dict:
        """结果后处理——记录指标。"""
        self._metrics.append({"query": result.get("query", ""), "agent": result.get("agent", "")})
        result["analytics_tracked"] = True
        return result

    @property
    def metrics(self):
        """返回已记录指标的副本。"""
        return self._metrics.copy()
