from typing import Any, Dict, List, Optional
from ..recipe import Recipe
from .base import BaseAdapter
import os


class QianwenAdapter(BaseAdapter):
    """Map Agent Assembler Recipe to Qianwen (Tongyi) Agent Format.
    
    Qianwen agents (百炼/通义) require:
    - name: Agent name
    - description: Brief description
    - system_prompt: Core instructions
    - model: LLM model selection
    
    This adapter generates Chinese-optimized prompts.
    """

    PLATFORM_NAME = "Qianwen"

    def __init__(self, skills_dir: Optional[str] = None):
        """Initialize with optional skills directory for JIT loading."""
        self.skills_dir = skills_dir

    def _load_skills(self, recipe: Recipe) -> str:
        """Load skill contents and format as prompt section."""
        if not self.skills_dir:
            return "(未配置技能目录)"

        sections = []
        for skill_name in recipe.skills:
            skill_path = os.path.join(self.skills_dir, skill_name, "SKILL.md")
            if os.path.exists(skill_path):
                with open(skill_path, "r", encoding="utf-8") as f:
                    sections.append(f"### 技能: {skill_name}\n{f.read()}")
            else:
                sections.append(f"### 技能: {skill_name}\n[警告: 技能文件未找到]")

        return "\n\n".join(sections)

    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """Export recipe as Qianwen-compatible agent configuration."""
        # Build system prompt in Chinese
        system_prompt = f"# 角色设定\n你是一个专业的 **{recipe.name}** 助手。\n\n"

        if recipe.notes:
            system_prompt += f"## 背景信息\n{recipe.notes}\n\n"

        system_prompt += "## 可用技能与指令\n"
        skills_content = self._load_skills(recipe)
        system_prompt += skills_content

        system_prompt += "\n\n## 执行规则\n"
        system_prompt += "- 严格按照技能指令执行任务\n"
        system_prompt += "- 如果用户请求不匹配任何技能，提供通用帮助\n"
        system_prompt += "- 保持回答简洁、专业、准确\n"

        # Construct Qianwen DSL
        agent_config = {
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

        return agent_config

    def validate(self, recipe: Recipe) -> List[str]:
        """Validate recipe against Qianwen platform constraints."""
        errors = []
        if len(recipe.name) > 30:
            errors.append(f"智能体名称 \'{recipe.name}\' 超过 30 字符限制。")
        if not recipe.name:
            errors.append("智能体名称不能为空。")
        # Check for valid routing if specified
        valid_routings = [
            None, "engineering-stage-agent", "finance-agent",
            "operations-venue-agent", "project-pmo-agent",
            "digital-tech-agent", "planning-agent",
            "marketing-promotion-agent", "legal-agent",
            "agriculture-agent", "guandan-agent", "gr-agent", "media-agent"
        ]
        if recipe.routing and recipe.routing not in valid_routings:
            errors.append(f"路由目标 \'{recipe.routing}\' 不在有效 Agent 列表中。")
        return errors
