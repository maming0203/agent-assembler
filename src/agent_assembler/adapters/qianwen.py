from typing import Any, Dict, List, Optional

from ..recipe import Recipe
from .base import BaseAdapter


class QianwenAdapter(BaseAdapter):
    """Map Agent Assembler Recipe to Qianwen (Tongyi) Agent Format."""

    PLATFORM_NAME = "Qianwen"

    # Chinese localization for skill loading
    SKILL_HEADER_PREFIX = "### 技能:"
    SKILL_NOT_FOUND_MSG = "[警告: 技能文件未找到]"
    NO_SKILLS_DIR_MSG = "(未配置技能目录)"

    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """Export recipe as Qianwen-compatible agent configuration."""
        system_prompt = f"# 角色设定\n你是一个专业的 **{recipe.name}** 助手。\n\n"

        if recipe.notes:
            system_prompt += f"## 背景信息\n{recipe.notes}\n\n"

        system_prompt += "## 可用技能与指令\n"
        system_prompt += self._load_skills(recipe)

        system_prompt += "\n\n## 执行规则\n"
        system_prompt += "- 严格按照技能指令执行任务\n"
        system_prompt += "- 如果用户请求不匹配任何技能，提供通用帮助\n"
        system_prompt += "- 保持回答简洁、专业、准确\n"

        return {
            "name": recipe.name,
            "description": recipe.notes or f"智能体: {recipe.name}",
            "system_prompt": system_prompt,
            "welcome_message": f"你好，我是{recipe.name}助手，请问有什么可以帮您？",
            "model": "qwen-max",
            "parameters": {
                "temperature": 0.7,
                "top_p": 0.8,
                "max_tokens": 2000
            },
            "metadata": {
                "source": "agent-assembler",
                "recipe_name": recipe.name,
                "trigger_keywords": recipe.trigger_keywords,
                "skills_count": len(recipe.skills),
                "routing": recipe.routing
            }
        }

    def validate(self, recipe: Recipe) -> List[str]:
        """Validate recipe against Qianwen platform constraints."""
        errors = []
        if not recipe.name:
            errors.append("智能体名称不能为空。")
        elif len(recipe.name) > 30:
            errors.append(f"智能体名称 '{recipe.name}' 超过 30 字符限制。")
        valid_routings = [
            None, "engineering-stage-agent", "finance-agent",
            "operations-venue-agent", "project-pmo-agent",
            "digital-tech-agent", "planning-agent",
            "marketing-promotion-agent", "legal-agent",
            "agriculture-agent", "guandan-agent", "gr-agent", "media-agent"
        ]
        if recipe.routing and recipe.routing not in valid_routings:
            errors.append(f"路由目标 '{recipe.routing}' 不在有效 Agent 列表中。")
        return errors
