"""Test autocraft v2 fixes."""
import sys, os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api_gateway.autocraft import (
    _load_recipe_schema_text,
    _validate_recipe_json,
    _extract_json_from_response,
    sanitize,
    _generate_skill_md,
    SKILL_AUTO_DIR,
)

def test_schema():
    schema = _load_recipe_schema_text()
    assert len(schema) > 50, f"Schema too short: {len(schema)}"
    assert "name" in schema
    assert "trigger_keywords" in schema
    print(f"PASS: schema loaded ({len(schema)} chars)")

def test_validation():
    valid = {"name": "test", "trigger_keywords": ["a", "b"], "skills": ["x"], "notes": "t"}
    assert _validate_recipe_json(valid) == [], f"Valid failed: {_validate_recipe_json(valid)}"
    
    e = _validate_recipe_json({"trigger_keywords": ["a", "b"]})
    assert any("name" in err for err in e)
    
    e = _validate_recipe_json({"name": "t", "trigger_keywords": ["one"]})
    assert any("2" in err for err in e)
    
    e = _validate_recipe_json({"name": "t", "trigger_keywords": ["a", "b"], "skills": [{"bad": True}]})
    assert any("string" in err for err in e)
    
    print("PASS: validation (4 cases)")

def test_json_extraction():
    # ```json block with surrounding text
    t1 = 'Here:\n```json\n{"name": "test", "trigger_keywords": ["a", "b"]}\n```\nDone.'
    r1 = _extract_json_from_response(t1)
    assert r1 and r1.get("name") == "test", f"json block failed: {r1}"
    
    # Bare JSON
    t2 = '{"name": "bare", "trigger_keywords": ["x", "y"]}'
    r2 = _extract_json_from_response(t2)
    assert r2 and r2.get("name") == "bare", f"bare failed: {r2}"
    
    # Plain ``` block
    t3 = '```\n{"name": "plain", "trigger_keywords": ["p", "q"]}\n```'
    r3 = _extract_json_from_response(t3)
    assert r3 and r3.get("name") == "plain", f"plain failed: {r3}"
    
    print("PASS: JSON extraction (3 cases)")

def test_sanitize():
    assert sanitize("hello world!") == "hello_world_"
    assert len(sanitize("a" * 50)) <= 30
    print("PASS: sanitize")

def test_skill_gen():
    with tempfile.TemporaryDirectory() as td:
        import api_gateway.autocraft as ac
        old = ac.SKILL_AUTO_DIR
        ac.SKILL_AUTO_DIR = td
        
        path = _generate_skill_md("calc_profit", "利润分析", ["利润", "盈利"])
        assert path.endswith(".md"), f"Expected .md: {path}"
        assert os.path.exists(path)
        content = open(path, encoding="utf-8").read()
        assert "利润分析" in content
        assert "角色定义" in content
        assert "工作流程" in content
        
        ac.SKILL_AUTO_DIR = old
    
    print("PASS: skill .md generation")

if __name__ == "__main__":
    test_schema()
    test_validation()
    test_json_extraction()
    test_sanitize()
    test_skill_gen()
    print("\nALL AUTOCRAFT FIXES VERIFIED")
