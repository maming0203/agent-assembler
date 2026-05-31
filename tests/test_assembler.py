
import os
import sys
import tempfile
import json

# Add parent dir to path to test local package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_assembler import Assembler

def test_basic_assembly():
    # Create temporary dirs for test
    with tempfile.TemporaryDirectory() as tmpdir:
        recipes_dir = os.path.join(tmpdir, "recipes")
        skills_dir = os.path.join(tmpdir, "skills")
        os.makedirs(recipes_dir)
        os.makedirs(os.path.join(skills_dir, "skill_A"))
        
        # Create dummy recipe
        recipe = {
            "name": "test_recipe",
            "trigger_keywords": ["test", "demo"],
            "skills": ["skill_A"]
        }
        with open(os.path.join(recipes_dir, "test.json"), "w") as f:
            json.dump(recipe, f)
            
        # Create dummy skill
        with open(os.path.join(skills_dir, "skill_A", "SKILL.md"), "w") as f:
            f.write("# Skill A\nContent A")
            
        # Run Assembler
        assembler = Assembler(recipes_dir, skills_dir)
        result = assembler.assemble("Please run a test demo")
        
        assert result["status"] == "assembled", f"Status mismatch: {result['status']}"
        assert result["recipe"] == "test_recipe"
        assert "Content A" in result["system_prompt"]
        print("✅ Test Passed: Basic Assembly")

if __name__ == "__main__":
    test_basic_assembly()
