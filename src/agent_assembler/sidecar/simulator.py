"""Simulator Sidecar——角色扮演、谈判训练。"""

from .base import SidecarBase


class Simulator(SidecarBase):
    """模拟器——角色扮演、谈判训练。"""

    name = "simulator"

    def pre_process(self, query: str) -> str:
        """查询前处理——标记模拟模式。"""
        return f"[模拟模式] {query}"

    def post_process(self, result: dict) -> dict:
        """结果后处理——标记模拟器激活。"""
        result["simulator_mode"] = True
        return result
