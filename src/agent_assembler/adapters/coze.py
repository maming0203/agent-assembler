from typing import Any, Dict, List, Optional
from ..recipe import Recipe
from .base import BaseAdapter
import os


class CozeAdapter(BaseAdapter):
    """Map Agent Assembler Recipe to Coze Bot Configuration.
    
    Coze Bots require:
    - bot_info.name
    - bot_info.description
    - bot_info.prompt_info.prompt (system instruction)
    - bot_info.onboarding_info.prologue (welcome message)
    
    This adapter injects Recipe + Skills content into the Coze DSL format.
    """

    PLATFORM_NAME = "Coze"

    def __init__(self, skills_dir: Optional[str] = None):
        """Initialize with optional skills directory for JIT loading."""
        self.skills_dir = skills_dir

    def _load_skills(self, recipe: Recipe) -> str:
        """Load skill contents and format as prompt section."""
        if not self.skills_dir:
            return "(Skills directory not configured)"

        sections = []
        for skill_name in recipe.skills:
            skill_path = os.path.join(self.skills_dir, skill_name, "SKILL.md")
            if os.path.exists(skill_path):
                with open(skill_path, "r", encoding="utf-8") as f:
                    sections.append(f"### Skill: {skill_name}\n{f.read()}")
            else:
                sections.append(f"### Skill: {skill_name}\n[Warning: Skill file not found]")

        return "\n\n".join(sections)

    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """Export recipe as Coze-compatible bot configuration."""
        # Build system prompt
        system_prompt = f"# Role\nYou are an AI assistant specialized in **{recipe.name}**.\n\n"

        if recipe.notes:
            system_prompt += f"## Context\n{recipe.notes}\n\n"

        system_prompt += "## Skills & Instructions\n"
        skills_content = self._load_skills(recipe)
        system_prompt += skills_content

        system_prompt += "\n\n## Execution Rules\n"
        system_prompt += "- Follow the skill instructions strictly.\n"
        system_prompt += "- If user query doesn\'t match any skill, fall back to general assistance.\n"

        # Construct Coze DSL
        bot_config = {
            "bot_info": {
                "name": recipe.name,
                "description": recipe.notes or f"Agent for {recipe.name}",
                "prompt_info": {
                    "prompt": system_prompt
                },
                "onboarding_info": {
                    "prologue": f"你好，我是{recipe.name}助手。请告诉我你需要什么帮助？"
                }
            },
            "model_info": {
                "model_name": "gpt-4o"
            },
            "metadata": {
                "source": "agent-assembler",
                "recipe_name": recipe.name,
                "trigger_keywords": recipe.trigger_keywords,
                "skills_count": len(recipe.skills)
            }
        }

        return bot_config

    def validate(self, recipe: Recipe) -> List[str]:
        """Validate recipe against Coze platform constraints."""
        errors = []
        if len(recipe.name) > 50:
            errors.append(f"Bot name \'{recipe.name}\' exceeds 50 characters limit.")
        if not recipe.name:
            errors.append("Bot name cannot be empty.")
        if len(recipe.notes) > 500:
            errors.append("Bot description exceeds 500 characters limit.")
        return errors
