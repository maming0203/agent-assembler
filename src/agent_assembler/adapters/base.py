
from abc import ABC, abstractmethod
import os
from typing import Any, Dict, List

from ..recipe import Recipe


class BaseAdapter(ABC):
    """Base class for all platform adapters."""

    PLATFORM_NAME = "Base"

    # Override these in subclasses for localization
    SKILL_HEADER_PREFIX = "### Skill:"  # e.g. "### 技能:" for Qianwen
    SKILL_NOT_FOUND_MSG = "[Warning: Skill file not found]"
    NO_SKILLS_DIR_MSG = "(Skills directory not configured)"

    def __init__(self, skills_dir=None):
        self.skills_dir = skills_dir

    def _load_skills(self, recipe: Recipe) -> str:
        """Load skill contents and format as prompt section."""
        if not self.skills_dir:
            return self.NO_SKILLS_DIR_MSG

        sections = []
        for skill_name in recipe.skills:
            skill_path = os.path.join(self.skills_dir, skill_name, "SKILL.md")
            if os.path.exists(skill_path):
                with open(skill_path, "r", encoding="utf-8") as f:
                    sections.append(f"{self.SKILL_HEADER_PREFIX} {skill_name}\n{f.read()}")
            else:
                sections.append(f"{self.SKILL_HEADER_PREFIX} {skill_name}\n{self.SKILL_NOT_FOUND_MSG}")

        return "\n\n".join(sections)

    @abstractmethod
    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """Export recipe to target platform format."""
        pass

    @abstractmethod
    def validate(self, recipe: Recipe) -> List[str]:
        """Validate recipe against platform constraints."""
        pass

    def deploy(self, recipe: Recipe) -> bool:
        """Deploy agent to platform."""
        raise NotImplementedError("Deploy not implemented.")
