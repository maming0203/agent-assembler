import os
import json
from typing import List, Optional, Dict
from .recipe import Recipe

class Assembler:
    def __init__(self, recipes_dir: str, skills_dir: str):
        self.recipes_dir = recipes_dir
        self.skills_dir = skills_dir
        self.recipes: List[Recipe] = []
        self._load_recipes()

    def _load_recipes(self):
        if not os.path.exists(self.recipes_dir):
            raise FileNotFoundError(f"Recipes directory not found: {self.recipes_dir}")
            
        for file in os.listdir(self.recipes_dir):
            if file.endswith('.json'):
                try:
                    self.recipes.append(Recipe.from_json(os.path.join(self.recipes_dir, file)))
                except Exception as e:
                    print(f"Warning: Failed to load recipe {file}: {e}")

    def match(self, query: str) -> Optional[Recipe]:
        query_lower = query.lower()
        best_recipe = None
        max_score = 0
        
        for recipe in self.recipes:
            score = 0
            for kw in recipe.trigger_keywords:
                kw_lower = kw.lower()
                # Support multi-word keywords (AND logic)
                if " " in kw_lower:
                    if all(w in query_lower for w in kw_lower.split()):
                        score += 1
                else:
                    if kw_lower in query_lower:
                        score += 1
            
            if score > max_score:
                max_score = score
                best_recipe = recipe
                
        return best_recipe if max_score > 0 else None

    def assemble(self, query: str) -> Dict:
        recipe = self.match(query)
        
        if not recipe:
            return {"status": "no_recipe", "skills": [], "system_prompt": "", "matched_recipe": None}

        skills_content = []
        missing_skills = []
        
        for skill_rel_path in recipe.skills:
            full_path = os.path.join(self.skills_dir, skill_rel_path, "SKILL.md")
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    skills_content.append(f.read())
            else:
                missing_skills.append(skill_rel_path)
                print(f"Warning: Skill not found at {full_path}")

        if missing_skills:
            print(f"Warning: Missing skills for recipe '{recipe.name}': {missing_skills}")

        prompt_parts = []
        if recipe.routing:
            prompt_parts.append(f"[ROUTING: Route this task to '{recipe.routing}']")
        
        prompt_parts.append("### Active Skills Context:")
        for i, content in enumerate(skills_content):
            # Use real newlines
            prompt_parts.append(f"--- Skill {i+1} ---\n{content}\n")
            
        prompt_parts.append(f"### User Query:\n{query}")

        return {
            "status": "assembled" if skills_content else "partial",
            "recipe": recipe.name,
            "skills_loaded": len(skills_content),
            "skills_missing": len(missing_skills),
            "routing": recipe.routing,
            "system_prompt": "\n".join(prompt_parts)
        }
