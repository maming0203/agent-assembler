"""
Test the AutoCraft pipeline logic (extraction, validation, writing) with mock LLM responses.

Scenarios:
1. Markdown Code Block: Response contains ```json { ... } ```
2. Raw JSON: Response contains just { ... } wrapped in text
3. Invalid JSON: Response contains invalid JSON -> Should fail validation
4. Missing Keys: JSON lacks 'name' or 'trigger_keywords' -> Should fail validation
5. Full pipeline: valid extraction + validation -> writes file to ~/Desktop/配方/AutoCreated/test_recipe.json
"""

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_gateway import _extract_json_from_response, _validate_recipe_json, AUTO_DIR

# ── Test helpers ──
pass_count = 0
fail_count = 0

def check(name, condition, detail=""):
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  ✅ PASS: {name}")
    else:
        fail_count += 1
        print(f"  ❌ FAIL: {name}{' — ' + detail if detail else ''}")

# ============================================================
# SCENARIO 1: Markdown Code Block
# ============================================================
print("=" * 60)
print("SCENARIO 1: Markdown fenced code block (```json ... ```)")
print("=" * 60)

md_response = """好的，这是为您生成的配方：

```json
{
  "name": "税务咨询助手",
  "trigger_keywords": ["税", "增值税", "纳税", "个税"],
  "skills": ["tax_calc"],
  "notes": "适用于中国大陆税务场景"
}
```

希望这个配方对您有帮助！"""

result1 = _extract_json_from_response(md_response)
check("Extracts dict from ```json block", result1 is not None)
check("name field correct", result1.get("name") == "税务咨询助手", f"got: {result1.get('name')}")
check("trigger_keywords correct", result1.get("trigger_keywords") == ["税", "增值税", "纳税", "个税"], f"got: {result1.get('trigger_keywords')}")
check("skills field present", result1.get("skills") == ["tax_calc"], f"got: {result1.get('skills')}")

# ============================================================
# SCENARIO 2: Raw JSON wrapped in text
# ============================================================
print()
print("=" * 60)
print("SCENARIO 2: Raw JSON wrapped in conversational text")
print("=" * 60)

raw_response = """Sure! Here's the recipe you need:
{"name": "农业评估专家", "trigger_keywords": ["农业", "作物", "受灾", "农田"], "notes": "农业领域专用"}
Let me know if you need anything else."""

result2 = _extract_json_from_response(raw_response)
check("Extracts dict from raw text", result2 is not None)
check("name field correct", result2.get("name") == "农业评估专家", f"got: {result2.get('name')}")
check("trigger_keywords correct", result2.get("trigger_keywords") == ["农业", "作物", "受灾", "农田"], f"got: {result2.get('trigger_keywords')}")

# ============================================================
# SCENARIO 3: Invalid JSON (malformed)
# ============================================================
print()
print("=" * 60)
print("SCENARIO 3: Invalid JSON (missing quotes, broken syntax)")
print("=" * 60)

invalid_json_md = """```json
{name: 税务助手, trigger_keywords: [税, 增值税]}
```"""

result3 = _extract_json_from_response(invalid_json_md)
check("Returns None for invalid JSON in code block", result3 is None)

invalid_json_raw = """Here is the result: {name: broken, trigger_keywords: [abc}"""
result3b = _extract_json_from_response(invalid_json_raw)
check("Returns None for invalid JSON in raw text", result3b is None)

# ============================================================
# SCENARIO 4: Missing required keys
# ============================================================
print()
print("=" * 60)
print("SCENARIO 4: Missing required keys (validation)")
print("=" * 60)

# 4a: Missing 'name'
no_name = {"trigger_keywords": ["税", "增值税"]}
errors4a = _validate_recipe_json(no_name)
check("Detects missing 'name'", any("name" in e for e in errors4a), f"errors: {errors4a}")

# 4b: Missing 'trigger_keywords'
no_kw = {"name": "Test Recipe"}
errors4b = _validate_recipe_json(no_kw)
check("Detects missing 'trigger_keywords'", any("trigger_keywords" in e for e in errors4b), f"errors: {errors4b}")

# 4c: Empty trigger_keywords list
empty_kw = {"name": "Test Recipe", "trigger_keywords": []}
errors4c = _validate_recipe_json(empty_kw)
check("Detects empty trigger_keywords list", any("empty" in e.lower() for e in errors4c), f"errors: {errors4c}")

# 4d: trigger_keywords not a list
kw_not_list = {"name": "Test Recipe", "trigger_keywords": "税"}
errors4d = _validate_recipe_json(kw_not_list)
check("Detects trigger_keywords not a list", any("list" in e.lower() for e in errors4d), f"errors: {errors4d}")

# 4e: name is empty string
empty_name = {"name": "  ", "trigger_keywords": ["税"]}
errors4e = _validate_recipe_json(empty_name)
check("Detects empty/whitespace name", any("non-empty" in e.lower() for e in errors4e), f"errors: {errors4e}")

# 4f: Valid recipe should pass
valid_recipe = {
    "name": "利润计算器",
    "trigger_keywords": ["利润", "营收", "成本"],
    "skills": ["calc"],
    "notes": "Test note"
}
errors4f = _validate_recipe_json(valid_recipe)
check("Valid recipe produces no errors", len(errors4f) == 0, f"errors: {errors4f}")

# ============================================================
# SCENARIO 5: Full pipeline — extract + validate + write file
# ============================================================
print()
print("=" * 60)
print("SCENARIO 5: Full pipeline (extract -> validate -> write)")
print("=" * 60)

# Prepare: clean up any previous test file
test_file = os.path.join(AUTO_DIR, "test_recipe.json")
if os.path.exists(test_file):
    os.remove(test_file)
    print(f"  Cleaned up previous test file: {test_file}")

# Simulate LLM response
mock_llm_response = """我已为您生成了配方：

```json
{
  "name": "测试配方_模拟",
  "trigger_keywords": ["测试", "模拟", "验证"],
  "skills": ["test_skill"],
  "notes": "This is a simulated recipe for pipeline testing",
  "routing": {"priority": "normal"},
  "engine_config": {"model": "qwen-max"}
}
```

请查收。"""

# Step 1: Extract
extracted = _extract_json_from_response(mock_llm_response)
check("Pipeline: extraction succeeded", extracted is not None)

if extracted:
    # Step 2: Validate
    v_errors = _validate_recipe_json(extracted)
    check("Pipeline: validation passed", len(v_errors) == 0, f"errors: {v_errors}")

    if not v_errors:
        # Step 3: Write (simulate the file-writing logic from auto_craft_and_run)
        os.makedirs(AUTO_DIR, exist_ok=True)
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(extracted, f, indent=2, ensure_ascii=False)

        # Step 4: Verify file exists and content is correct
        check("Pipeline: file exists on disk", os.path.exists(test_file))

        if os.path.exists(test_file):
            with open(test_file, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            check("Pipeline: file content matches — name", saved_data.get("name") == "测试配方_模拟", f"got: {saved_data.get('name')}")
            check("Pipeline: file content matches — keywords", saved_data.get("trigger_keywords") == ["测试", "模拟", "验证"], f"got: {saved_data.get('trigger_keywords')}")
            check("Pipeline: file content matches — skills", saved_data.get("skills") == ["test_skill"], f"got: {saved_data.get('skills')}")
            check("Pipeline: file content matches — notes", saved_data.get("notes") == "This is a simulated recipe for pipeline testing", f"got: {saved_data.get('notes')}")
            check("Pipeline: file content matches — routing", saved_data.get("routing") == {"priority": "normal"}, f"got: {saved_data.get('routing')}")
            check("Pipeline: file content matches — engine_config", saved_data.get("engine_config") == {"model": "qwen-max"}, f"got: {saved_data.get('engine_config')}")

            # Pretty-print the written file for inspection
            print()
            print("  📄 Written file content:")
            with open(test_file, "r", encoding="utf-8") as f:
                for line in f:
                    print(f"     {line.rstrip()}")
        else:
            check("Pipeline: file exists on disk", False, "file was not created")
    else:
        print("  ⚠️  Validation failed — skipping write step")
else:
    print("  ⚠️  Extraction failed — skipping validation and write steps")

# ============================================================
# Edge cases
# ============================================================
print()
print("=" * 60)
print("EDGE CASES")
print("=" * 60)

# Edge 1: Response with no JSON at all
no_json = "This is just plain text with no JSON whatsoever."
edge1 = _extract_json_from_response(no_json)
check("Returns None for text with no JSON", edge1 is None)

# Edge 2: Response with multiple code blocks, first is non-JSON
multi_block = """Here's some code:
```python
print("hello")
```

And here's the recipe:
```json
{"name": "Edge Case", "trigger_keywords": ["edge"]}
```
"""
edge2 = _extract_json_from_response(multi_block)
check("Extracts from second block when first is non-JSON", edge2 is not None)
if edge2:
    check("Correct name from multi-block", edge2.get("name") == "Edge Case", f"got: {edge2.get('name')}")

# Edge 3: Generic fenced block (no language tag)
generic_block = """```
{"name": "Generic Block", "trigger_keywords": ["generic", "test"]}
```"""
edge3 = _extract_json_from_response(generic_block)
check("Extracts from generic ``` block (no lang tag)", edge3 is not None)
if edge3:
    check("Correct name from generic block", edge3.get("name") == "Generic Block", f"got: {edge3.get('name')}")

# Edge 4: Extra fields in dict should not cause validation errors
extra_fields = {
    "name": "Extra Fields Recipe",
    "trigger_keywords": ["extra"],
    "custom_field": "should be ignored",
    "another_one": 42
}
edge4 = _validate_recipe_json(extra_fields)
check("Validation ignores unknown fields", len(edge4) == 0, f"errors: {edge4}")

# ============================================================
# Summary
# ============================================================
print()
print("=" * 60)
print(f"SUMMARY: {pass_count} passed, {fail_count} failed, {pass_count + fail_count} total")
print("=" * 60)

if fail_count == 0:
    print("🎉 All tests passed! AutoCraft pipeline is ready for ECS deployment.")
else:
    print(f"⚠️  {fail_count} test(s) failed. Review failures above before deployment.")

sys.exit(0 if fail_count == 0 else 1)
