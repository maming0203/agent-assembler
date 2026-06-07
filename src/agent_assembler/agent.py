"""Agent 类 + Agent Spec — 组装前的蓝图与运行时实例"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────
# AgentSpec: 蓝图
# ──────────────────────────────────────────

@dataclass
class AgentSpec:
    """Agent 规格定义——组装前的蓝图。
    
    AgentSpec 是 Agent Assembler 的一等公民。
    它描述了一个 Agent 的所有静态属性：角色、配方、技能、Sidecar 插件。
    Assembler 根据 Spec 组装出可执行的 Agent 实例。
    """
    name: str                              # Agent 名称
    role: str = ""                         # 角色描述
    system_prompt: str = ""                # 系统提示词
    recipes: list[str] = field(default_factory=list)   # 关联配方列表
    skills: list[str] = field(default_factory=list)    # 技能列表
    sidecars: list[str] = field(default_factory=list)  # Sidecar 插件列表
    platform: str = "standalone"           # 目标平台
    model: str = "qwen3.6-plus"           # 默认模型
    config: dict[str, Any] = field(default_factory=dict)
    
    def to_recipe_names(self) -> list[str]:
        """返回配方名列表"""
        return self.recipes
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "name": self.name,
            "role": self.role,
            "system_prompt": self.system_prompt,
            "recipes": self.recipes,
            "skills": self.skills,
            "sidecars": self.sidecars,
            "platform": self.platform,
            "model": self.model,
            "config": self.config,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSpec:
        """从 dict 反序列化"""
        return cls(
            name=data.get("name", ""),
            role=data.get("role", ""),
            system_prompt=data.get("system_prompt", ""),
            recipes=data.get("recipes", []),
            skills=data.get("skills", []),
            sidecars=data.get("sidecars", []),
            platform=data.get("platform", "standalone"),
            model=data.get("model", "qwen3.6-plus"),
            config=data.get("config", {}),
        )
    
    @classmethod
    def from_json(cls, path: str) -> AgentSpec:
        """从 JSON 文件加载 Agent Spec"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def to_json(self, path: str):
        """保存 Agent Spec 到 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def validate(self) -> list[str]:
        """验证 Agent Spec 完整性，返回错误列表"""
        errors: list[str] = []
        if not self.name:
            errors.append("Agent name is required")
        if not self.system_prompt:
            errors.append("system_prompt is required")
        if not self.recipes and not self.skills:
            errors.append("At least one recipe or skill is required")
        return errors


# ──────────────────────────────────────────
# Agent: 运行时实例
# ──────────────────────────────────────────

class Agent:
    """可执行的 Agent 实例——由 Assembler 组装后的产物。
    
    Agent 持有：
    - AgentSpec（静态蓝图）
    - Sidecar 插件集合（动态热插拔）
    - 对话历史
    """
    
    def __init__(self, spec: AgentSpec):
        self.spec = spec
        self._sidecars: dict[str, Any] = {}
        self._history: list[dict[str, str]] = []
    
    def add_sidecar(self, name: str, instance: Any):
        """热插拔 Sidecar 插件"""
        self._sidecars[name] = instance
    
    def remove_sidecar(self, name: str):
        """卸载 Sidecar 插件"""
        self._sidecars.pop(name, None)
    
    def has_sidecar(self, name: str) -> bool:
        return name in self._sidecars
    
    def list_sidecars(self) -> list[str]:
        return list(self._sidecars.keys())
    
    def run(self, query: str) -> dict:
        """执行 Agent。
        
        流程：
        1. 记录用户输入到历史
        2. 调用 Sidecar pre_process 链
        3. 返回结果（后续接入 LLM 调用）
        """
        self._history.append({"role": "user", "content": query})
        
        processed_query = query
        for name, sidecar in self._sidecars.items():
            if hasattr(sidecar, "pre_process"):
                processed_query = sidecar.pre_process(processed_query)
        
        result = {
            "agent": self.spec.name,
            "query": query,
            "processed_query": processed_query,
            "sidecars_active": list(self._sidecars.keys()),
            "model": self.spec.model,
        }
        
        # 调用 Sidecar post_process 链
        for name, sidecar in self._sidecars.items():
            if hasattr(sidecar, "post_process"):
                result = sidecar.post_process(result)
        
        self._history.append({"role": "assistant", "content": str(result)})
        return result
    
    @property
    def history(self) -> list[dict[str, str]]:
        return self._history.copy()
    
    def clear_history(self):
        self._history.clear()
    
    def __repr__(self) -> str:
        return f"Agent(name={self.spec.name!r}, sidecars={list(self._sidecars.keys())})"
