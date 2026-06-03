
from typing import Any, Dict, List
from ..recipe import Recipe
from .base import BaseAdapter
import json

class QianwenAdapter(BaseAdapter):
    PLATFORM_NAME = "Qianwen"
    
    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """
        Map Agent Assembler Recipe to Qianwen (Tongyi) Agent Format.
        """
        
        system_prompt = f"你是 {recipe.name} 助手。\n"
        if recipe.notes:
            system_prompt += f"## 背景\n{recipe.notes}\n\n"
        system_prompt += "## 技能与指令\n"
        
        agent_config = {
            "name": recipe.name,
            "description": recipe.notes or f"Agent for {recipe.name}",
            "system_prompt": system_prompt,
            "welcome_message": f"你好，我是 {recipe.name}。",
            "model": "qwen-max", # Default
            "metadata": {
                "source": "agent-assembler",
                "version": "0.1.0"
            }
        }
        
        return agent_config

    def validate(self, recipe: Recipe) -> List[str]:
        errors = []
        if len(recipe.name) > 30: # Qianwen might have shorter name limits
            errors.append("Agent name is too long for Qianwen.")
        return errors
