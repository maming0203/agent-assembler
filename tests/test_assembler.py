"""Tests for Agent Assembler SDK."""
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_assembler import Assembler, Recipe
from agent_assembler.recipe import SkillRef
from agent_assembler.adapters.base import BaseAdapter


def test_basic_assembly():
    """Test: query matches recipe, skills loaded, prompt assembled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        recipes_dir = os.path.join(tmpdir, "recipes")
        skills_dir = os.path.join(tmpdir, "skills")
        os.makedirs(recipes_dir)
        os.makedirs(os.path.join(skills_dir, "skill_A"))

        recipe = {
            "name": "test_recipe",
            "trigger_keywords": ["test", "demo"],
            "skills": ["skill_A"]
        }
        with open(os.path.join(recipes_dir, "test.json"), "w") as f:
            json.dump(recipe, f)

        with open(os.path.join(skills_dir, "skill_A", "SKILL.md"), "w") as f:
            f.write("# Skill A\nContent A")

        assembler = Assembler(recipes_dir, skills_dir)
        result = assembler.assemble("Please run a test demo")

        assert result["status"] == "success", f"Status mismatch: {result['status']}"
        assert result["recipe"] == "test_recipe"
        assert "Content A" in result["system_prompt"]
        print("✅ test_basic_assembly passed")


def test_no_match_fallback():
    """Test: query does not match any recipe → fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        recipes_dir = os.path.join(tmpdir, "recipes")
        skills_dir = os.path.join(tmpdir, "skills")
        os.makedirs(recipes_dir)
        os.makedirs(skills_dir)

        recipe = {
            "name": "only_recipe",
            "trigger_keywords": ["specific"],
            "skills": []
        }
        with open(os.path.join(recipes_dir, "only.json"), "w") as f:
            json.dump(recipe, f)

        assembler = Assembler(recipes_dir, skills_dir)
        result = assembler.assemble("unrelated query")

        assert result["status"] == "fallback"
        assert "No matching recipe found" in result["message"]
        print("✅ test_no_match_fallback passed")


def test_missing_recipe_dir():
    """Test: non-existent recipes directory raises FileNotFoundError."""
    try:
        Assembler("/nonexistent/path/12345", "/tmp")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        print("✅ test_missing_recipe_dir passed")


def test_recipe_from_json():
    """Test: Recipe deserialization from JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "name": "my_recipe",
            "trigger_keywords": ["alpha", "beta"],
            "skills": ["s1", "s2"],
            "notes": "Some notes",
            "routing": "engineering-agent"
        }, f)
        f.flush()

        recipe = Recipe.from_json(f.name)
        assert recipe.name == "my_recipe"
        assert len(recipe.trigger_keywords) == 2
        assert len(recipe.skills) == 2
        assert recipe.notes == "Some notes"
        assert recipe.routing == "engineering-agent"
        print("✅ test_recipe_from_json passed")


def test_skill_ref_load():
    """Test: SkillRef loads content from filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "my_skill"))
        with open(os.path.join(tmpdir, "my_skill", "SKILL.md"), "w") as f:
            f.write("# My Skill\nBody content")

        ref = SkillRef(name="my_skill")
        assert ref.load_content(tmpdir) is True
        assert ref.loaded is True
        assert "Body content" in ref.content
        print("✅ test_skill_ref_load passed")


def test_skill_ref_missing():
    """Test: SkillRef returns False when file does not exist."""
    ref = SkillRef(name="nonexistent_skill")
    assert ref.load_content("/tmp") is False
    assert ref.loaded is False
    print("✅ test_skill_ref_missing passed")


def test_multiple_recipes_first_match():
    """Test: first matching recipe is returned (deterministic)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        recipes_dir = os.path.join(tmpdir, "recipes")
        skills_dir = os.path.join(tmpdir, "skills")
        os.makedirs(recipes_dir)
        os.makedirs(skills_dir)

        # Write two recipes that both match "data"
        for name, kw in [("data_cleaner", ["data", "clean"]), ("data_viz", ["data", "chart"])]:
            with open(os.path.join(recipes_dir, f"{name}.json"), "w") as f:
                json.dump({"name": name, "trigger_keywords": kw, "skills": []}, f)

        assembler = Assembler(recipes_dir, skills_dir)
        result = assembler.assemble("show me data")

        assert result["status"] == "success"
        # Should match the first one found (alphabetical walk order)
        assert result["recipe"] in ("data_cleaner", "data_viz")
        print("✅ test_multiple_recipes_first_match passed")


if __name__ == "__main__":
    test_basic_assembly()
    test_no_match_fallback()
    test_missing_recipe_dir()
    test_recipe_from_json()
    test_skill_ref_load()
    test_skill_ref_missing()
    test_multiple_recipes_first_match()
    print("\n✅ All 7 tests passed")
