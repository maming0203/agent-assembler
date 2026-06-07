"""Test: auto_craft_and_run basic flow."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from api_gateway.autocraft import _validate_recipe_json, sanitize, _extract_json_from_response


def test_validate_recipe_valid():
    """Test: valid recipe passes validation."""
    valid = {
        "name": "test recipe",
        "trigger_keywords": ["test", "demo"],
        "skills": ["skill_a"],
    }
    errors = _validate_recipe_json(valid)
    assert len(errors) == 0
    print("✅ test_validate_recipe_valid passed")


def test_validate_recipe_missing_name():
    """Test: missing name field fails validation."""
    invalid = {"trigger_keywords": ["test"]}
    errors = _validate_recipe_json(invalid)
    assert len(errors) > 0
    assert "name" in errors[0].lower()
    print("✅ test_validate_recipe_missing_name passed")


def test_validate_recipe_empty_keywords():
    """Test: empty trigger_keywords fails validation."""
    invalid = {"name": "test", "trigger_keywords": []}
    errors = _validate_recipe_json(invalid)
    assert len(errors) > 0
    print("✅ test_validate_recipe_empty_keywords passed")


def test_sanitize_chinese():
    """Test: sanitize handles Chinese characters."""
    result = sanitize("帮我做数据分析")
    assert len(result) <= 20
    assert "数据" in result
    print("✅ test_sanitize_chinese passed")


def test_extract_json_from_code_block():
    """Test: extract JSON from markdown code block."""
    text = 'Here is the recipe:\n```json\n{"name": "test", "trigger_keywords": ["a"]}\n```\nDone.'
    result = _extract_json_from_response(text)
    assert result is not None
    assert result["name"] == "test"
    print("✅ test_extract_json_from_code_block passed")


def test_extract_json_from_plain_text():
    """Test: extract JSON from plain text without code blocks."""
    text = '{"name": "plain", "trigger_keywords": ["x"]}'
    result = _extract_json_from_response(text)
    assert result is not None
    assert result["name"] == "plain"
    print("✅ test_extract_json_from_plain_text passed")
