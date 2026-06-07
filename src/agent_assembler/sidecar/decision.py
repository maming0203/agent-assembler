"""Decision Engine Sidecar——对查询结果做"红黄绿"判定。"""

from .base import SidecarBase


class DecisionEngine(SidecarBase):
    """决策引擎——对查询结果做"红黄绿"判定。"""

    name = "decision"

    def pre_process(self, query: str) -> str:
        """查询前处理（骨架）。"""
        return query

    def post_process(self, result: dict) -> dict:
        """结果后处理——附加判定标记（骨架）。"""
        result["decision"] = "green"
        result["decision_note"] = "Decision Engine active (skeleton)"
        return result
