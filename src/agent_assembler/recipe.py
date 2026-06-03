
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path

@dataclass
class SkillRef:
    name: str
    content: str = ""
    path: str = ""
    loaded: bool = False

    def load_content(self, root_dir: str):
        """Load the actual skill content from file system."""
        # Try to find the skill file
        # Structure: {root_dir}/{skill_name}/SKILL.md
        potential_path = os.path.join(root_dir, self.name, "SKILL.md")
        if os.path.exists(potential_path):
            with open(potential_path, "r", encoding="utf-8") as f:
                self.content = f.read()
            self.path = potential_path
            self.loaded = True
            return True
        return False

@dataclass
class Recipe:
    """Recipe maps user intent to specific skills."""
    name: str
    trigger_keywords: List[str]
    skills: List[str] = field(default_factory=list) # Skill names
    notes: str = ""
    routing: Optional[str] = None
    _skill_refs: List[SkillRef] = field(default_factory=list, init=False)

    @property
    def skill_refs(self) -> List[SkillRef]:
        return self._skill_refs

    def load_skills(self, skills_dir: str):
        """Load all skills defined in this recipe."""
        self._skill_refs = []
        for skill_name in self.skills:
            ref = SkillRef(name=skill_name)
            if ref.load_content(skills_dir):
                self._skill_refs.append(ref)
            else:
                print(f"[Warning] Skill not found: {skill_name} in {skills_dir}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_file: str = ""):
        return cls(
            name=data.get("name", Path(source_file).stem),
            trigger_keywords=data.get("trigger_keywords", []),
            skills=data.get("skills", []),
            notes=data.get("notes", ""),
            routing=data.get("routing")
        )

    @classmethod
    def from_json(cls, path: str):
        with open(path, 'r', encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, path)
