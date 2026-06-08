"""Simulator — 模拟器（角色扮演、谈判训练）。

支持沉浸式模拟场景：价格谈判、合同审核、客户服务等。
Agent 可通过 Simulator 切换到特定角色，进行训练或验证。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .base import SidecarBase


@dataclass
class Scene:
    """模拟场景定义。"""
    id: str
    name: str                           # 场景名称
    role: str                           # 用户扮演的角色
    opponent: str                       # Agent 扮演的对手角色
    background: str                     # 背景设定
    objective: str                      # 用户目标
    difficulty: str = "medium"          # easy | medium | hard
    hints: list[str] = field(default_factory=list)  # 提示信息
    success_criteria: str = ""          # 成功标准

    def to_prompt(self) -> str:
        """生成 system prompt。"""
        parts = [
            f"# 模拟场景: {self.name}",
            f"## 你的角色",
            f"你是{self.opponent}。",
            f"",
            f"## 背景",
            f"{self.background}",
            f"",
            f"## 对方角色（用户扮演）",
            f"用户扮演{self.role}。",
            f"",
            f"## 目标",
            f"你的目标是{self.objective}。",
            f"",
            f"## 难度: {self.difficulty}",
        ]
        if self.difficulty == "hard":
            parts.append("提示：你要表现得更难谈判，不轻易让步。")
        elif self.difficulty == "easy":
            parts.append("提示：你要表现得容易沟通，愿意合作。")

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "opponent": self.opponent,
            "background": self.background,
            "objective": self.objective,
            "difficulty": self.difficulty,
            "hints": self.hints,
            "success_criteria": self.success_criteria,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            role=data.get("role", ""),
            opponent=data.get("opponent", ""),
            background=data.get("background", ""),
            objective=data.get("objective", ""),
            difficulty=data.get("difficulty", "medium"),
            hints=data.get("hints", []),
            success_criteria=data.get("success_criteria", ""),
        )

    @classmethod
    def from_json(cls, path: str) -> "Scene":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# ──────────────────────────────────────────
# 预置场景
# ──────────────────────────────────────────

BUILTIN_SCENES: list[Scene] = [
    Scene(
        id="price-negotiation",
        name="价格谈判",
        role="客户",
        opponent="供应商销售代表",
        background="你是一家 SaaS 公司的销售代表，客户想购买你们的年度服务，但觉得价格太高。客户预算有限，但需求明确。",
        objective="在不降价超过 20% 的前提下达成交易，最好能签两年约。",
        difficulty="medium",
        hints=["先了解客户的预算范围", "强调产品价值而非价格", "可以尝试打包优惠", "底线是 8 折"],
        success_criteria="成交价 ≥ 原价的 80%，或签两年约",
    ),
    Scene(
        id="contract-review",
        name="合同审核谈判",
        role="乙方代表",
        opponent="甲方采购经理",
        background="你代表甲方，要审核一份软件开发合同。关键争议点：付款周期、知识产权归属、违约责任。",
        objective="争取最有利的合同条款：30% 预付款、知识产权归甲方、违约金 10%。",
        difficulty="hard",
        hints=["知识产权是核心争议", "付款周期可以妥协", "违约金不能让步"],
        success_criteria="知识产权归甲方 + 违约金 ≥ 5%",
    ),
    Scene(
        id="customer-complaint",
        name="客户投诉处理",
        role="不满的客户",
        opponent="客服经理",
        background="客户购买了产品但遇到问题，情绪比较激动，要求退款。",
        objective="安抚客户情绪，找出问题根因，尽量保留客户，必要时提供补偿。",
        difficulty="easy",
        hints=["先道歉表示理解", "不要急于推卸责任", "找出具体问题再给方案"],
        success_criteria="客户同意不退款或接受替代方案",
    ),
]


class Simulator(SidecarBase):
    """模拟器——角色扮演、谈判训练等沉浸式场景。

    用法:
        sim = Simulator()
        sim.load_scene(BUILTIN_SCENES[0])  # 加载预置场景
        prompt = sim.build_prompt()
        # prompt 可用作 system prompt

        # 或直接挂载到 Agent
        agent.add_sidecar("simulator", sim)
        agent.run("你好，我们聊聊合作")
    """
    name = "simulator"
    version = "0.2.0"

    def __init__(self, scenes_dir: str | None = None):
        self._scenes: dict[str, Scene] = {}
        self._active_scene: Scene | None = None
        self._session_log: list[dict[str, str]] = []

        # 加载预置场景
        for scene in BUILTIN_SCENES:
            self._scenes[scene.id] = scene

        # 加载自定义场景目录
        if scenes_dir and os.path.exists(scenes_dir):
            self._load_scenes_from_dir(scenes_dir)

    def _load_scenes_from_dir(self, scenes_dir: str):
        """从目录加载 JSON 场景文件。"""
        for root, _, files in os.walk(scenes_dir):
            for f in files:
                if f.endswith(".json"):
                    try:
                        scene = Scene.from_json(os.path.join(root, f))
                        self._scenes[scene.id] = scene
                    except Exception:
                        pass

    def add_scene(self, scene: Scene):
        """添加场景。"""
        self._scenes[scene.id] = scene

    def remove_scene(self, scene_id: str) -> bool:
        """移除场景。"""
        if scene_id in self._scenes:
            del self._scenes[scene_id]
            return True
        return False

    def list_scenes(self) -> list[dict[str, str]]:
        """列出所有可用场景。"""
        return [
            {
                "id": s.id,
                "name": s.name,
                "difficulty": s.difficulty,
                "role": s.role,
                "opponent": s.opponent,
            }
            for s in self._scenes.values()
        ]

    def get_scene(self, scene_id: str) -> Scene | None:
        """获取场景。"""
        return self._scenes.get(scene_id)

    def load_scene(self, scene_id: str) -> bool:
        """加载并激活场景。"""
        scene = self._scenes.get(scene_id)
        if scene:
            self._active_scene = scene
            self._session_log = []
            return True
        return False

    def build_prompt(self, system_prompt: str | None = None) -> str:
        """构建模拟器 system prompt。"""
        if not self._active_scene:
            return system_prompt or ""

        parts = [self._active_scene.to_prompt()]
        if system_prompt:
            parts.append(system_prompt)
        return "\n\n".join(parts)

    def get_hint(self) -> str | None:
        """获取当前场景提示。"""
        if not self._active_scene or not self._active_scene.hints:
            return None
        # 根据会话进度返回不同提示
        turn = len(self._session_log) // 2
        hints = self._active_scene.hints
        return hints[min(turn, len(hints) - 1)]

    def evaluate_session(self) -> dict[str, Any]:
        """评估当前会话结果。"""
        if not self._active_scene:
            return {"error": "No active scene"}

        return {
            "scene": self._active_scene.name,
            "turns": len(self._session_log) // 2,
            "success_criteria": self._active_scene.success_criteria,
            "session_log": self._session_log,
        }

    def pre_process(self, query: str) -> str:
        if self._active_scene:
            self._session_log.append({"role": "user", "content": query})
            hint = self.get_hint()
            if hint:
                return f"[模拟场景: {self._active_scene.name}] [提示: {hint}]\n{query}"
            return f"[模拟场景: {self._active_scene.name}]\n{query}"
        return query

    def post_process(self, result: dict) -> dict:
        if self._active_scene:
            self._session_log.append({"role": "assistant", "content": result.get("reply", "")})
            result["simulator"] = {
                "scene": self._active_scene.name,
                "turn": len(self._session_log) // 2,
                "hint_available": bool(self._active_scene.hints),
            }
        return result

    @property
    def active_scene(self) -> Scene | None:
        return self._active_scene

    @property
    def session_log(self) -> list[dict[str, str]]:
        return list(self._session_log)

    def clear_session(self):
        self._session_log.clear()

    def meta(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "scenes_loaded": str(len(self._scenes)),
            "active_scene": self._active_scene.name if self._active_scene else "none",
        }
