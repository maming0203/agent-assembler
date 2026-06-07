"""Decision Engine — 决策引擎（红黄绿判定）"""
from __future__ import annotations

from .base import SidecarBase


class DecisionEngine(SidecarBase):
    """决策引擎——对 Agent 输出做"红黄绿"判定。
    
    当前为骨架，后续接入真实判定逻辑（如规则引擎、LLM 判定）。
    """
    name = "decision"
    version = "0.1.0"
    
    def pre_process(self, query: str) -> str:
        return query
    
    def post_process(self, result: dict) -> dict:
        # 骨架：默认绿灯，后续接入真实判定
        result["decision"] = "green"
        result["decision_note"] = "Decision Engine active (skeleton)"
        return result
