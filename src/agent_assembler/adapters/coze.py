
from typing import Any, Dict, List
from ..recipe import Recipe
from .base import BaseAdapter
import json

class CozeAdapter(BaseAdapter):
    PLATFORM_NAME = "Coze"
    
    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """
        Map Agent Assembler Recipe to Coze Bot Configuration.
        Coze Bots are defined by:
        - Name
        - Description
        - Prompt (System Instruction)
        - Plugins/Tools (Our Skills could be mapped here or embedded in Prompt)
        """
        
        # Load skills content to embed in prompt if needed
        # For Coze, we usually construct a "System Prompt" that utilizes the logic.
        
        system_prompt = f"You are an AI assistant specialized in {recipe.name}.\n"
        
        if recipe.notes:
            system_prompt += f"## Context\n{recipe.notes}\n\n"
            
        system_prompt += "## Available Skills & Instructions\n"
        
        # Since Coze doesn't natively support "Recipe" files, 
        # we inject the Recipe logic into the System Prompt.
        
        # In a real scenario, we might load the skill content here.
        # But for the DSL export, we focus on structure.
        
        # Construct the Bot config
        bot_config = {
            "bot_info": {
                "name": recipe.name,
                "description": recipe.notes or f"Agent for {recipe.name}",
                "prompt_info": {
                    "prompt": system_prompt
                },
                "onboarding_info": {
                    "prologue": f"你好，我是 {recipe.name} 助手。"
                }
            },
            "model_info": {
                "model_name": "gpt-4o" # Default, user can change in Coze
            },
            "metadata": {
                "source": "agent-assembler",
                "version": "0.1.0"
            }
        }
        
        return bot_config

    def validate(self, recipe: Recipe) -> List[str]:
        errors = []
        # Coze name limit: usually short
        if len(recipe.name) > 50:
            errors.append("Bot name is too long for Coze.")
        return errors
