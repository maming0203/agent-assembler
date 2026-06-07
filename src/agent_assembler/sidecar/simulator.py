"""Simulator — 模拟器（角色扮演、谈判训练）"""
from __future__ import annotations

from .base import SidecarBase


class Simulator(SidecarBase):
    """模拟器——角色扮演、谈判训练等沉浸式模拟场景。
    
    当前为骨架，后续接入真实角色设定、场景配置。
    """
    name = "simulator"
    version = "0.1.0"
    
    def pre_process(self, query: str) -> str:
        return f"[模拟模式] {query}"
    
    def post_process(self, result: dict) -> dict:
        result["simulator_mode"] = True
        return result
