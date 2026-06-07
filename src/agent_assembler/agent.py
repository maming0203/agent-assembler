"""Agent 类与 Agent Spec 定义——组装前后的核心产物。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentSpec:
    """Agent 规格定义——组装前的蓝图。"""

    name: str                              # Agent 名称
    role: str                              # 角色描述
    system_prompt: str                     # 系统提示词
    recipes: list[str] = field(default_factory=list)   # 关联的配方名列表
    skills: list[str] = field(default_factory=list)    # 技能列表
    sidecars: list[str] = field(default_factory=list)  # Sidecar 插件列表
    platform: str = "standalone"           # 目标平台
    model: str = "qwen3.6-plus"           # 默认模型
    config: dict[str, Any] = field(default_factory=dict)

    def to_recipe_names(self) -> list[str]:
        """返回配方名列表。"""
        return self.recipes

    def validate(self) -> list[str]:
        """验证 Agent Spec 完整性，返回错误列表。"""
        errors = []
        if not self.name:
            errors.append("Agent name is required")
        if not self.system_prompt:
            errors.append("system_prompt is required")
        if not self.recipes and not self.skills:
            errors.append("At least one recipe or skill is required")
        return errors


class Agent:
    """可执行的 Agent 实例——由 Assembler 组装后的产物。"""

    def __init__(self, spec: AgentSpec, assembler=None):
        self.spec = spec
        self._assembler = assembler
        self._sidecars = {}
        self._history = []

    def add_sidecar(self, name: str, instance):
        """热插拔 Sidecar 插件。"""
        self._sidecars[name] = instance

    def remove_sidecar(self, name: str):
        """卸载 Sidecar 插件。"""
        self._sidecars.pop(name, None)

    def run(self, query: str) -> dict:
        """执行 Agent。"""
        self._history.append({"role": "user", "content": query})
        result = {
            "agent": self.spec.name,
            "query": query,
            "sidecars_active": list(self._sidecars.keys()),
            "model": self.spec.model,
        }
        # 调用 Sidecar 预处理
        processed_query = query
        for name, sidecar in self._sidecars.items():
            if hasattr(sidecar, "pre_process"):
                processed_query = sidecar.pre_process(processed_query)

        result["processed_query"] = processed_query
        self._history.append({"role": "assistant", "content": str(result)})
        return result

    @property
    def history(self) -> list[dict]:
        """返回对话历史副本。"""
        return self._history.copy()
