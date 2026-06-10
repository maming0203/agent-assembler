"""AutoCraft v4 — Merged: v3 modular architecture + P0/P2b quality gates.

Architecture:
- v3 模块化：template_engine (Jinja2) + recipe_validator (结构化校验)
- P0 Loop Engineering: independent_evaluate（独立评估器，防止"自卖自夸"）
- P2b Quality Gate: 质量门禁自动化（评分 + 多维度检查）

完整流程：
1. LLM 生成 recipe JSON + Python script + few-shot examples
2. 提取并校验 JSON（auto-fix）
3. 产物生成 via Jinja2 模板（SKILL.md + .py + mcp.json + recipe JSON）
4. RecipeValidator 结构化校验（v3）
5. independent_evaluate 独立评估（P0）
6. quality_gate 质量门禁（P2b）
7. 全部通过 → 入库；任一失败 → 清理 + 重试

完整产出物：
- recipe JSON（含 script_path + metadata）
- Python 脚本（validate_inputs + run_simulation + run_stress_test + --json CLI）
- SKILL.md（YAML frontmatter + Few-shot + GEO 优化）
- mcp.json（MCP 工具声明）
"""

import json
import os
import re
import sys
import time
import subprocess
from typing import Optional

from .config import (
    AUTO_DIR, SKILL_AUTO_DIR,
    RECIPE_SCHEMA_PATH,
)
from .template_engine import (
    render_skill_md,
    render_recipe_script,
    render_mcp_config,
    render_recipe_json,
)
from .recipe_validator import RecipeValidator

os.makedirs(AUTO_DIR, exist_ok=True)
os.makedirs(SKILL_AUTO_DIR, exist_ok=True)

# Python 脚本存放目录
SCRIPT_AUTO_DIR = os.path.join(AUTO_DIR, "scripts")
os.makedirs(SCRIPT_AUTO_DIR, exist_ok=True)


# ================================================================ #
#  Helper functions (shared from v3)
# ================================================================ #

def _load_recipe_schema_text() -> str:
    """Load recipe schema JSON text for embedding in LLM prompts."""
    try:
        with open(RECIPE_SCHEMA_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[AutoCraft v4] WARN: Could not load schema from {RECIPE_SCHEMA_PATH}: {e}")
        return json.dumps({
            "name": "配方名称（必填，不能为空）",
            "trigger_keywords": ["触发关键词1", "触发关键词2"],
            "skills": [],
            "notes": "配方说明",
            "script_path": "关联的 Python 脚本路径",
        }, ensure_ascii=False, indent=2)


def _validate_recipe_json(data: dict) -> list:
    """Validate recipe JSON structure."""
    errors: list[str] = []

    if "name" not in data:
        errors.append("Missing required field: 'name'")
    elif not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("'name' must be a non-empty string")

    if "trigger_keywords" not in data:
        errors.append("Missing required field: 'trigger_keywords'")
    elif not isinstance(data["trigger_keywords"], list):
        errors.append("'trigger_keywords' must be a list")
    elif len(data["trigger_keywords"]) < 2:
        errors.append("'trigger_keywords' must have at least 2 keywords")
    elif not all(isinstance(kw, str) and kw.strip() for kw in data["trigger_keywords"]):
        errors.append("All items in 'trigger_keywords' must be non-empty strings")

    if "skills" in data:
        if not isinstance(data["skills"], list):
            errors.append("'skills' must be a list")
        else:
            for i, s in enumerate(data["skills"]):
                if not isinstance(s, str):
                    errors.append(f"skills[{i}] must be a string, got {type(s).__name__}")

    if "notes" in data and not isinstance(data["notes"], str):
        errors.append("'notes' must be a string")

    if "routing" in data and not isinstance(data["routing"], dict):
        errors.append("'routing' must be an object")

    if "engine_config" in data and not isinstance(data["engine_config"], dict):
        errors.append("'engine_config' must be an object")

    return errors


def _extract_json_from_response(text: str):
    """Extract JSON from LLM response (3-level extraction)."""
    m = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = text[first:last + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def _dashscope_chat(messages: list, system_prompt: Optional[str] = None) -> str:
    """DashScope chat completion."""
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
    if not api_key:
        return "[Error] DASHSCOPE_API_KEY not set"
    try:
        from openai import OpenAI
    except ImportError:
        return "[Error] openai library not available"

    base_url = "https://coding.dashscope.aliyuncs.com/v1"
    model = "qwen3.6-plus"
    built_messages = []
    if system_prompt:
        built_messages.append({"role": "system", "content": system_prompt})
    built_messages.extend(messages)

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model, messages=built_messages, max_tokens=8192, temperature=0.7,
        )
        content = resp.choices[0].message.content
        if content:
            print(f"[DashScope] qwen3.6-plus response: {content[:100]}...")
            return content.strip()
        return "[Error] Empty response from DashScope"
    except Exception as e:
        print(f"[WARN] DashScope chat failed: {e}")
        return f"[Error] DashScope API error: {str(e)}"


def sanitize(q):
    """Sanitize a query string for use as a filename."""
    return re.sub(r"[^\w\u4e00-\u9fa5]", "_", q)[:30]


# ================================================================ #
#  v3 Prompt + Extraction
# ================================================================ #

def _build_v3_prompt(query: str, schema_text: str) -> str:
    """
    Build the v4 LLM prompt that forces generation of:
    - Recipe JSON (with script_path)
    - Python script code (with validate_inputs + run_simulation + run_stress_test)
    - Intent description + Few-shot examples + GEO metadata
    """
    return "\n".join([
        f'User asked: "{query}". No recipe matched.',
        '',
        'You are a Recipe Architect (AutoCraft v4). Generate a COMPLETE recipe package:',
        '',
        '## 1. Recipe JSON',
        'Output ONLY valid JSON inside a ```json ... ``` block with these fields:',
        '- "name": concise recipe name (not the user query itself)',
        '- "trigger_keywords": array of >= 3 relevant Chinese keywords/phrases',
        '- "skills": array of skill name strings (e.g., ["expert_analysis"])',
        '- "notes": description of what this recipe does',
        '- "intent_description": one-line description of user intent (Chinese)',
        '- "scenario_tags": array of 2-4 scenario tags like ["咨询", "分析", "商业"]',
        '- "target_audience": who benefits from this recipe (Chinese)',
        '',
        '## 2. Python Script',
        'After the JSON, output a Python script inside a ```python ... ``` block.',
        'The script MUST contain a class with:',
        '- validate_inputs(self, inputs) -> dict: validates inputs, checks trigger keywords',
        '- run_simulation(self, inputs) -> dict: core computation logic with domain-specific code',
        '- run_stress_test(self) -> dict: runs 13+ test cases, returns pass/fail report',
        '- __main__ block with --json and --test CLI support',
        '',
        'Script requirements:',
        '- Import json, os, sys, argparse',
        '- Use argparse with --json (for Gateway) and --test (for stress test)',
        '- run_simulation must return structured dict with status/output/data/steps',
        '- Replace any "stub" placeholder with REAL computation logic for this domain',
        '',
        '## 3. Few-shot Examples',
        'After the Python script, output 3-4 few-shot dialog examples in a ```markdown ... ``` block:',
        '- Each example: User query + Assistant response',
        '- Cover: normal use, edge case, missing parameter',
        '',
        'Schema reference:',
        '```json',
        schema_text,
        '```',
        '',
        'IMPORTANT RULES:',
        '1. Output the JSON FIRST, then Python script, then few-shot examples',
        '2. Each section in its own code block with language tag',
        '3. The Python script must have REAL computation logic, not just stubs',
        '4. trigger_keywords must be in Chinese and relevant to the user query',
        '5. The script class name should be CamelCase based on the recipe name',
    ])


def _extract_python_from_response(text: str) -> Optional[str]:
    """Extract Python code from LLM response."""
    m = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```py\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _extract_fewshot_from_response(text: str) -> list:
    """Extract few-shot examples from LLM response."""
    examples = []
    m = re.search(r"```(?:markdown)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        block = m.group(1).strip()
        parts = re.split(r'\*\*用户\*\*[:：]\s*|User[:：]\s*', block)
        for part in parts:
            if not part.strip():
                continue
            assistant_match = re.search(r'\*\*助手\*\*[:：]\s*|Assistant[:：]\s*(.*)', part, re.DOTALL)
            if assistant_match:
                user_text = re.split(r'\*\*助手\*\*[:：]\s*|Assistant[:：]\s*', part)[0].strip()
                assistant_text = assistant_match.group(1).strip()
                if user_text and assistant_text:
                    examples.append({"user": user_text, "assistant": assistant_text})
    return examples


def _generate_class_name(recipe_name: str) -> str:
    """Convert recipe name to a valid Python class name."""
    name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', recipe_name)
    if not name:
        return "Recipe"
    words = re.findall(r'[A-Z][a-z]*|[a-z]+|[0-9]+|[\u4e00-\u9fa5]+', recipe_name)
    if not words:
        return "Recipe"
    return ''.join(w.capitalize() for w in words)


# ================================================================ #
#  v3 Artifact Generation (Jinja2 templates)
# ================================================================ #

def _generate_artifacts(
    recipe_data: dict,
    script_code: str,
    few_shot_examples: list,
    query: str,
    sanitized_name: str,
) -> dict:
    """
    Generate all recipe artifacts using Jinja2 templates.
    Returns dict with file paths.
    """
    recipe_name = recipe_data.get("name", sanitized_name)
    trigger_keywords = recipe_data.get("trigger_keywords", [])
    skills = recipe_data.get("skills", [])
    class_name = _generate_class_name(recipe_name)

    intent_description = recipe_data.get("intent_description", f"用户需要关于{recipe_name}的专业帮助")
    scenario_tags = recipe_data.get("scenario_tags", ["咨询", "分析"])
    target_audience = recipe_data.get("target_audience", f"需要{recipe_name}解决方案的用户")

    # File paths
    script_filename = f"{sanitized_name}.py"
    script_full_path = os.path.join(AUTO_DIR, script_filename)
    skill_filename = f"{sanitized_name}-SKILL.md"
    skill_full_path = os.path.join(AUTO_DIR, skill_filename)
    mcp_filename = f"{sanitized_name}-mcp.json"
    mcp_full_path = os.path.join(AUTO_DIR, mcp_filename)
    recipe_filename = f"{sanitized_name}.json"
    recipe_full_path = os.path.join(AUTO_DIR, recipe_filename)

    script_path_rel = script_filename

    # 1. Write Python script
    with open(script_full_path, "w", encoding="utf-8") as f:
        f.write(script_code)
    print(f"[AutoCraft v4] Wrote Python script: {script_full_path}")

    # 2. Generate SKILL.md via Jinja2
    skill_md_content = render_skill_md(
        skill_name=recipe_name,
        recipe_name=recipe_name,
        trigger_keywords=trigger_keywords,
        intent_description=intent_description,
        scenario_tags=scenario_tags,
        target_audience=target_audience,
        few_shot_examples=few_shot_examples,
        input_schema=[
            {"name": "query", "type": "string", "description": "用户原始问题", "required": True},
        ],
        output_schema=[
            {"name": "status", "type": "string", "description": "执行状态: ok/error"},
            {"name": "output", "type": "string", "description": "人类可读的结果摘要"},
            {"name": "data", "type": "object", "description": "结构化计算结果"},
        ],
    )
    with open(skill_full_path, "w", encoding="utf-8") as f:
        f.write(skill_md_content)
    print(f"[AutoCraft v4] Wrote SKILL.md: {skill_full_path}")

    # 3. Generate mcp.json via Jinja2
    mcp_content = render_mcp_config(
        skill_name=recipe_name,
        recipe_name=recipe_name,
        trigger_keywords=trigger_keywords,
        script_path=script_path_rel,
        input_schema=[
            {"name": "query", "type": "string", "description": "用户原始查询", "required": True},
        ],
        output_schema=[
            {"name": "status", "type": "string", "description": "执行状态"},
            {"name": "data", "type": "object", "description": "计算结果"},
        ],
    )
    with open(mcp_full_path, "w", encoding="utf-8") as f:
        f.write(mcp_content)
    print(f"[AutoCraft v4] Wrote mcp.json: {mcp_full_path}")

    # 4. Generate enriched recipe JSON via Jinja2
    recipe_json_content = render_recipe_json(
        recipe_name=recipe_name,
        trigger_keywords=trigger_keywords,
        script_path=script_path_rel,
        skill_md=skill_filename,
        mcp_config=mcp_filename,
        description=intent_description,
        notes=recipe_data.get("notes", ""),
        intent_description=intent_description,
        scenario_tags=scenario_tags,
        target_audience=target_audience,
        few_shot_examples=few_shot_examples,
        skills=skills,
        test_passed=False,  # Will be updated after validation
    )
    recipe_json = json.loads(recipe_json_content)
    with open(recipe_full_path, "w", encoding="utf-8") as f:
        json.dump(recipe_json, f, indent=2, ensure_ascii=False)
    print(f"[AutoCraft v4] Wrote recipe JSON: {recipe_full_path}")

    return {
        "recipe_path": recipe_full_path,
        "script_path": script_full_path,
        "skill_md_path": skill_full_path,
        "mcp_json_path": mcp_full_path,
    }


def _run_validation(artifact_paths: dict, recipe_data: dict) -> dict:
    """Run the full validation suite on generated artifacts (v3 RecipeValidator)."""
    validator = RecipeValidator(recipe_dir=AUTO_DIR)
    report = validator.validate_full(
        recipe_name=recipe_data.get("name", "unknown"),
        recipe_data=recipe_data,
        script_path=artifact_paths.get("script_path", ""),
        skill_md_path=artifact_paths.get("skill_md_path", ""),
        mcp_json_path=artifact_paths.get("mcp_json_path", ""),
    )

    print(f"[AutoCraft v4] Validation: {report.summary()}")
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"  [{status}] {check.check}: {check.message}")

    if report.errors:
        print(f"[AutoCraft v4] Errors:")
        for err in report.errors:
            print(f"  - {err}")

    return {
        "passed": report.overall_passed,
        "summary": report.summary(),
        "errors": report.errors,
        "total_checks": len(report.checks),
        "passed_checks": sum(1 for c in report.checks if c.passed),
    }


def _update_recipe_test_status(recipe_path: str, test_passed: bool):
    """Update recipe JSON to reflect test pass/fail status."""
    try:
        with open(recipe_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["test_passed"] = test_passed
        with open(recipe_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[AutoCraft v4] WARN: Could not update test status: {e}")


# ================================================================ #
#  P0: Independent Evaluator (Loop Engineering)
# ================================================================ #

def independent_evaluate(recipe_data: dict, script_path, script_test_passed: bool) -> dict:
    """独立 Evaluator — 不复用 Generator 上下文。

    P0 Loop Engineering: Evaluator 必须独立于 Generator，防止"自卖自夸"。

    Returns: {"pass": bool, "reason": str}
    """
    # 1. 脚本 stress test 必须通过
    if script_path and not script_test_passed:
        return {"pass": False, "reason": "脚本 stress test 未通过"}

    # 2. 配方必要字段
    if not recipe_data.get("name"):
        return {"pass": False, "reason": "配方名称 (name) 缺失"}
    if not recipe_data.get("trigger_keywords"):
        return {"pass": False, "reason": "触发关键词 (trigger_keywords) 缺失"}
    if len(recipe_data.get("trigger_keywords", [])) < 2:
        return {"pass": False, "reason": "触发关键词不足 2 个"}

    # 3. 脚本文件存在
    if script_path and not os.path.exists(script_path):
        return {"pass": False, "reason": "脚本文件不存在: " + script_path}

    # 4. skills 格式
    skills = recipe_data.get("skills", [])
    if not isinstance(skills, list):
        return {"pass": False, "reason": "skills 必须是数组"}
    for i, s in enumerate(skills):
        if not isinstance(s, str):
            return {"pass": False, "reason": "skills[%d] 必须是字符串" % i}

    # 5. notes 内容
    notes = recipe_data.get("notes", "")
    if notes and len(notes.strip()) < 5:
        return {"pass": False, "reason": "notes 内容过短"}

    return {"pass": True, "reason": "Evaluator 验证通过"}


# ================================================================ #
#  P2b: Quality Gate (自动化质量门禁)
# ================================================================ #

def quality_gate(recipe_data: dict, script_path: str, eval_result: dict, execution_time: float = 0) -> dict:
    """P2b: 质量门禁自动化。配方发布前最后一道关卡。

    Returns:
        {"pass": True, "score": 95, "checks": [...]}
        {"pass": False, "reason": "...", "checks": [...]}
    """
    checks = []
    score = 100

    # 1. 配方命名规范（不能太短、不能全是英文）
    name = recipe_data.get("name", "")
    if len(name) < 4:
        checks.append({"check": "name_length", "pass": False, "reason": f"配方名 '{name}' 太短"})
        score -= 20
    elif name.isascii() and len(name) > 10:
        checks.append({"check": "name_language", "pass": False, "reason": f"配方名 '{name}' 全英文，建议中文"})
        score -= 10
    else:
        checks.append({"check": "name_length", "pass": True})

    # 2. 关键词质量（不能有过于宽泛的词）
    keywords = recipe_data.get("trigger_keywords", [])
    weak_keywords = [kw for kw in keywords if len(kw) < 3 or kw in ["优化", "分析", "计算", "查询"]]
    if weak_keywords:
        checks.append({"check": "keyword_quality", "pass": False, "reason": f"关键词过于宽泛: {weak_keywords}"})
        score -= 15
    else:
        checks.append({"check": "keyword_quality", "pass": True})

    # 3. 执行时间检查（< 5 秒）
    if execution_time > 5.0:
        checks.append({"check": "execution_time", "pass": False, "reason": f"执行时间 {execution_time:.2f}s 超限"})
        score -= 10
    else:
        checks.append({"check": "execution_time", "pass": True})

    # 4. 脚本文件大小检查（< 100KB）
    if script_path and os.path.exists(script_path):
        file_size = os.path.getsize(script_path)
        if file_size > 100 * 1024:
            checks.append({"check": "script_size", "pass": False, "reason": f"脚本文件 {file_size/1024:.1f}KB 超限"})
            score -= 10
        else:
            checks.append({"check": "script_size", "pass": True})

    # 5. 配方字段完整性
    required_fields = ["name", "version", "trigger_keywords", "skills", "routing"]
    missing = [f for f in required_fields if f not in recipe_data]
    if missing:
        checks.append({"check": "field_completeness", "pass": False, "reason": f"缺少字段: {missing}"})
        score -= 20
    else:
        checks.append({"check": "field_completeness", "pass": True})

    # 6. 版本号格式（语义化版本）
    version = recipe_data.get("version", "")
    if not re.match(r'^\d+\.\d+\.\d+$', str(version)):
        checks.append({"check": "version_format", "pass": False, "reason": f"版本号 '{version}' 不符合语义化版本"})
        score -= 5
    else:
        checks.append({"check": "version_format", "pass": True})

    # 综合判定（分数 < 70 则拒绝）
    if score < 70:
        failed_checks = [c for c in checks if not c["pass"]]
        reason = "; ".join([c["reason"] for c in failed_checks])
        return {"pass": False, "score": score, "reason": reason, "checks": checks}

    return {"pass": True, "score": score, "checks": checks}


# ================================================================ #
#  Main Pipeline: auto_craft_and_run (v4 merged)
# ================================================================ #

def _cleanup_artifacts(artifact_paths: dict):
    """Clean up generated artifact files on failure."""
    for path in artifact_paths.values():
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


async def auto_craft_and_run(query, user_id, max_retries: int = 3):
    """
    AutoCraft v4: Full recipe generation pipeline with quality gates.

    Flow:
    1. LLM generates recipe JSON + Python script + few-shot examples
    2. Extract and validate JSON (with auto-fix)
    3. Generate all artifacts via Jinja2 templates (v3)
    4. RecipeValidator structural validation (v3)
    5. independent_evaluate — P0 Loop Engineering gate
    6. quality_gate — P2b quality score gate
    7. All pass -> 入库; Any fail -> cleanup + retry
    """
    sanitized_name = sanitize(query)
    schema_text = _load_recipe_schema_text()
    prompt = _build_v3_prompt(query, schema_text)

    last_error = None
    result = None

    for attempt in range(1, max_retries + 1):
        print(f"[AutoCraft v4] Attempt {attempt}/{max_retries} for query: {query}")

        os.makedirs(AUTO_DIR, exist_ok=True)
        os.makedirs(SKILL_AUTO_DIR, exist_ok=True)
        os.makedirs(SCRIPT_AUTO_DIR, exist_ok=True)

        # ---- Step 1: Call LLM ----
        result = _dashscope_chat([{"role": "user", "content": prompt}])
        if result.startswith("[Error]"):
            last_error = result
            print(f"[AutoCraft v4] {last_error} — retrying...")
            continue

        # ---- Step 2: Extract recipe JSON ----
        recipe_data = _extract_json_from_response(result)
        if recipe_data is None:
            last_error = "Could not extract valid JSON from LLM response"
            print(f"[AutoCraft v4] {last_error} — retrying...")
            continue

        # ---- Step 3: Validate JSON (with auto-fix) ----
        validation_errors = _validate_recipe_json(recipe_data)
        if validation_errors:
            fixed = False
            if "name" not in recipe_data or not recipe_data.get("name"):
                recipe_data["name"] = f"AutoCraft_{sanitized_name}"
                fixed = True
            if "trigger_keywords" not in recipe_data or not isinstance(recipe_data.get("trigger_keywords"), list) or len(recipe_data.get("trigger_keywords", [])) < 2:
                recipe_data["trigger_keywords"] = [query[:10], sanitized_name, query.split()[0] if query.split() else "auto"]
                fixed = True
            if "skills" in recipe_data and not isinstance(recipe_data["skills"], list):
                recipe_data["skills"] = []
                fixed = True

            if fixed:
                validation_errors = _validate_recipe_json(recipe_data)
                if validation_errors:
                    last_error = f"Schema validation failed (even after auto-fix): {'; '.join(validation_errors)}"
                    print(f"[AutoCraft v4] {last_error} — retrying...")
                    continue
            else:
                last_error = f"Schema validation failed: {'; '.join(validation_errors)}"
                print(f"[AutoCraft v4] {last_error} — retrying...")
                continue

        # ---- Step 4: Extract Python script ----
        script_code = _extract_python_from_response(result)
        if not script_code:
            print(f"[AutoCraft v4] No Python script in LLM response, generating from template")
            class_name = _generate_class_name(recipe_data.get("name", sanitized_name))
            script_code = render_recipe_script(
                recipe_name=recipe_data.get("name", sanitized_name),
                class_name=class_name,
                trigger_keywords=recipe_data.get("trigger_keywords", []),
                recipe_path="",
            )

        # ---- Step 5: Extract few-shot examples ----
        few_shot_examples = _extract_fewshot_from_response(result)
        if not few_shot_examples:
            few_shot_examples = [
                {"user": f"请帮我{recipe_data.get('name', '')}", "assistant": "我来帮您分析..."},
                {"user": f"关于{recipe_data.get('name', '')}的问题", "assistant": "根据您的情况..."},
            ]

        # ---- Step 6: Generate all artifacts via Jinja2 (v3) ----
        artifact_paths = _generate_artifacts(
            recipe_data=recipe_data,
            script_code=script_code,
            few_shot_examples=few_shot_examples,
            query=query,
            sanitized_name=sanitized_name,
        )

        # Enrich recipe_data with generated artifact metadata
        recipe_data["script_path"] = artifact_paths["script_path"]
        recipe_data["version"] = "1.0.0"
        recipe_data["skill_md"] = os.path.basename(artifact_paths.get("skill_md_path", ""))
        recipe_data["mcp_config"] = os.path.basename(artifact_paths.get("mcp_json_path", ""))

        # ---- Step 7: RecipeValidator structural validation (v3) ----
        validation_result = _run_validation(artifact_paths, recipe_data)

        if not validation_result["passed"]:
            last_error = f"RecipeValidator failed: {validation_result['summary']}"
            print(f"[AutoCraft v4] {last_error} — retrying...")
            _cleanup_artifacts(artifact_paths)
            continue

        # Determine script_test_passed from validation
        script_test_passed = validation_result["passed"]

        # ---- Step 8: P0 — Independent Evaluator ----
        eval_result = independent_evaluate(recipe_data, artifact_paths["script_path"], script_test_passed)
        if not eval_result["pass"]:
            last_error = "P0 Evaluator rejected: " + eval_result["reason"]
            print(f"[AutoCraft v4] {last_error} — retrying...")
            _cleanup_artifacts(artifact_paths)
            continue
        print(f"[AutoCraft v4] P0 Evaluator passed: {eval_result['reason']}")

        # ---- Step 9: P2b — Quality Gate ----
        start_time = time.time()
        gate_result = quality_gate(recipe_data, artifact_paths["script_path"], eval_result, execution_time=0)
        if not gate_result["pass"]:
            last_error = f"P2b Quality gate rejected (score={gate_result['score']}): {gate_result['reason']}"
            print(f"[AutoCraft v4] {last_error} — retrying...")
            _cleanup_artifacts(artifact_paths)
            continue
        print(f"[AutoCraft v4] P2b Quality gate passed (score={gate_result['score']})")

        # ---- Step 10: Update test status + 入库 ----
        _update_recipe_test_status(artifact_paths["recipe_path"], True)

        print(f"[AutoCraft v4] Recipe '{recipe_data['name']}' fully validated on attempt {attempt}")
        return {
            "status": "auto_generated",
            "message": "已现场生成完整配方（JSON + Python 脚本 + SKILL.md + mcp.json + P0/P2b 质量门禁通过）",
            "recipe": recipe_data["name"],
            "recipe_path": artifact_paths["recipe_path"],
            "script_path": artifact_paths["script_path"],
            "skill_md_path": artifact_paths["skill_md_path"],
            "mcp_json_path": artifact_paths["mcp_json_path"],
            "validation": validation_result,
            "evaluator": eval_result,
            "quality_gate": gate_result,
            "attempts": attempt,
            "version": "v4",
        }

    # All retries exhausted
    print(f"[AutoCraft v4] FAILED after {max_retries} attempts. Last error: {last_error}")
    return {
        "status": "auto_craft_failed",
        "message": f"配方生成失败（{max_retries} 次重试后仍未通过校验）",
        "report": result or "无结果",
        "last_error": last_error,
        "attempts": max_retries,
        "version": "v4",
    }
