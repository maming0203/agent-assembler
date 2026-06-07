from typing import Any, Dict, List, Optional

from ..recipe import Recipe
from .base import BaseAdapter


class CozeAdapter(BaseAdapter):
    """Map Agent Assembler Recipe to Coze Bot Configuration."""

    PLATFORM_NAME = "Coze"

    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """Export recipe as Coze-compatible bot configuration."""
        system_prompt = f"# Role\nYou are an AI assistant specialized in **{recipe.name}**.\n\n"

        if recipe.notes:
            system_prompt += f"## Context\n{recipe.notes}\n\n"

        system_prompt += "## Skills & Instructions\n"
        system_prompt += self._load_skills(recipe)

        system_prompt += "\n\n## Execution Rules\n"
        system_prompt += "- Follow the skill instructions strictly.\n"
        system_prompt += "- If user query doesn't match any skill, fall back to general assistance.\n"

        return {
            "bot_info": {
                "name": recipe.name,
                "description": recipe.notes or f"Agent for {recipe.name}",
                "prompt_info": {"prompt": system_prompt},
                "onboarding_info": {
                    "prologue": f"你好，我是{recipe.name}助手。请告诉我你需要什么帮助？"
                }
            },
            "model_info": {"model_name": "coze-pro"},
            "metadata": {
                "source": "agent-assembler",
                "recipe_name": recipe.name,
                "trigger_keywords": recipe.trigger_keywords,
                "skills_count": len(recipe.skills),
            }
        }

    def validate(self, recipe: Recipe) -> List[str]:
        """Validate recipe against Coze platform constraints."""
        errors = []
        if not recipe.name:
            errors.append("Bot name cannot be empty.")
        elif len(recipe.name) > 50:
            errors.append(f"Bot name '{recipe.name}' exceeds 50 characters limit.")
        if recipe.notes and len(recipe.notes) > 500:
            errors.append("Bot description exceeds 500 characters limit.")
        return errors
