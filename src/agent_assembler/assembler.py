
import os
import json
import re
from typing import List, Optional, Dict
from .recipe import Recipe
from .agent import Agent, AgentSpec
from .sidecar.base import SidecarBus

class Assembler:
    """The core engine of Agent Assembler."""
    
    def __init__(self, recipes_dir: str, skills_dir: str):
        self.recipes_dir = os.path.abspath(recipes_dir)
        self.skills_dir = os.path.abspath(skills_dir)
        self.recipes: List[Recipe] = []
        
        self._load_recipes()

    def _load_recipes(self):
        """Load all recipes from the configured directory."""
        if not os.path.exists(self.recipes_dir):
            raise FileNotFoundError(f"Recipes directory not found: {self.recipes_dir}")
            
        for root, _, files in os.walk(self.recipes_dir):
            for file in files:
                if file.endswith('.json'):
                    path = os.path.join(root, file)
                    try:
                        recipe = Recipe.from_json(path)
                        # Pre-load skills? No, JIT load them when matched to save time/memory.
                        # But for SDK v1, maybe eager load is fine for small datasets.
                        # Let's do lazy loading in assemble() for better performance.
                        self.recipes.append(recipe)
                    except Exception as e:
                        print(f"Error loading recipe {path}: {e}")

    def match_recipe(self, query: str) -> Optional[Recipe]:
        """Find the best matching recipe for a user query."""
        query_lower = query.lower()
        matches = []
        
        for recipe in self.recipes:
            for keyword in recipe.trigger_keywords:
                if keyword.lower() in query_lower:
                    matches.append(recipe)
                    break # Found a match for this recipe
        
        if not matches:
            return None
            
        # Return the first match (can be improved with scoring later)
        return matches[0]

    def assemble(self, query: str) -> Dict:
        """Perform JIT assembly."""
        recipe = self.match_recipe(query)
        
        if not recipe:
            return {
                "status": "fallback",
                "message": "No matching recipe found.",
                "system_prompt": query # Pass through
            }
            
        # Load skills JIT
        recipe.load_skills(self.skills_dir)
        
        # Construct Prompt
        system_prompt = f"# Role\nYou are an AI assistant executing the task: {recipe.name}\n\n"
        
        if recipe.notes:
            system_prompt += f"## Context\n{recipe.notes}\n\n"
            
        system_prompt += "## Skills & Rules\n"
        
        for skill_ref in recipe.skill_refs:
            system_prompt += f"### Skill: {skill_ref.name}\n{skill_ref.content}\n\n"
            
        system_prompt += f"## User Query\n{query}"
        
        return {
            "status": "success",
            "recipe": recipe.name,
            "skills_loaded": [s.name for s in recipe.skill_refs],
            "system_prompt": system_prompt
        }

    def assemble_agent(self, spec: AgentSpec) -> Agent:
        """根据 AgentSpec 组装并返回可执行的 Agent 实例。

        复用现有的 assemble 逻辑加载配方和技能，然后包装为 Agent。
        """
        agent = Agent(spec, assembler=self)
        return agent
