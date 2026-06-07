"""AutoCraft module — recipe generation, schema validation, retry logic, LLM calls."""
import json
import os
import re
from typing import Optional

IS_CLOUD = os.path.exists("/data/jit")
if IS_CLOUD:
    AUTO_DIR = "/data/jit/recipes/AutoCreated"
    SKILL_AUTO_DIR = os.path.join(AUTO_DIR, "Skills")
else:
    AUTO_DIR = os.path.expanduser("~/Desktop/配方/AutoCreated")
    SKILL_AUTO_DIR = os.path.join(AUTO_DIR, "Skills")
os.makedirs(AUTO_DIR, exist_ok=True)
os.makedirs(SKILL_AUTO_DIR, exist_ok=True)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTOCRAFT_REF_DIR = os.path.join(PROJECT_ROOT, "autocraft", "references")
RECIPE_SCHEMA_PATH = os.path.join(AUTOCRAFT_REF_DIR, "recipe_schema.json")


def _load_recipe_schema_text() -> str:
    """Load recipe schema JSON text for embedding in LLM prompts."""
    try:
        with open(RECIPE_SCHEMA_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _validate_recipe_json(data: dict) -> list:
    """Manual validation of a recipe dict against the core schema rules."""
    errors: list[str] = []
    if "name" not in data:
        errors.append("Missing required field: 'name'")
    elif not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("'name' must be a non-empty string")
    if "trigger_keywords" not in data:
        errors.append("Missing required field: 'trigger_keywords'")
    elif not isinstance(data["trigger_keywords"], list):
        errors.append("'trigger_keywords' must be a list")
    elif len(data["trigger_keywords"]) == 0:
        errors.append("'trigger_keywords' must not be empty")
    elif not all(isinstance(kw, str) for kw in data["trigger_keywords"]):
        errors.append("All items in 'trigger_keywords' must be strings")
    if "skills" in data and not isinstance(data["skills"], list):
        errors.append("'skills' must be a list of strings")
    if "notes" in data and not isinstance(data["notes"], str):
        errors.append("'notes' must be a string")
    if "routing" in data and not isinstance(data["routing"], dict):
        errors.append("'routing' must be an object")
    if "engine_config" in data and not isinstance(data["engine_config"], dict):
        errors.append("'engine_config' must be an object")
    return errors


def _extract_json_from_response(text: str):
    """Extract the first valid JSON object from LLM response text."""
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
    """Direct DashScope chat completion via the OpenAI-compatible API."""
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
    return re.sub(r"[^\w\u4e00-\u9fa5]", "_", q)[:20]


def _generate_skill_py(skill_name: str, recipe_name: str) -> str:
    """Generate a minimal Python skill module for the given skill name."""
    class_name = re.sub(r"[^a-zA-Z0-9]", "", skill_name.title().replace("_", " ").replace("-", " "))
    if not class_name:
        class_name = "GenericSkill"
    skill_code = (
        '"""Auto-generated skill: ' + recipe_name + '"""\n'
        'import os\n'
        '\n'
        '\n'
        'class ' + class_name + ':\n'
        '    """Skill auto-generated by AutoCraft pipeline."""\n'
        '\n'
        '    def __init__(self, config=None):\n'
        '        self.config = config or {}\n'
        '        self.name = "' + skill_name + '"\n'
        '\n'
        '    def run(self, query: str, context: dict = None) -> str:\n'
        '        """Execute the skill logic."""\n'
        '        api_key = os.environ.get("DASHSCOPE_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")\n'
        '        if not api_key:\n'
        '            return f"[{self.name}] LLM API key not configured. Query: {query}"\n'
        '        try:\n'
        '            from openai import OpenAI\n'
        '            api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")\n'
        '            client = OpenAI(api_key=api_key, base_url=api_base)\n'
        '            resp = client.chat.completions.create(\n'
        '                model=os.environ.get("CHAT_MODEL_NAME", "qwen-plus"),\n'
        '                messages=[{"role": "user", "content": query}],\n'
        '                temperature=0.7,\n'
        '                max_tokens=2048,\n'
        '            )\n'
        '            return (resp.choices[0].message.content or "").strip()\n'
        '        except Exception as e:\n'
        '            return f"[{self.name}] Execution error: {str(e)}"\n'
    )
    skill_file = os.path.join(SKILL_AUTO_DIR, f"{skill_name}.py")
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(skill_code)
    # Verify importability
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(skill_name, skill_file)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print(f"[AutoCraft] Skill '{skill_name}' generated and importable: {skill_file}")
        else:
            print(f"[AutoCraft] Skill '{skill_name}' written (import check skipped): {skill_file}")
    except Exception as e:
        print(f"[AutoCraft] WARN: Skill '{skill_name}' import check failed: {e}")
    return skill_file


async def auto_craft_and_run(query, user_id, max_retries: int = 3):
    """Auto-generate a recipe + skill when no existing recipe matches."""
    sanitized_name = sanitize(query)
    recipe_path = os.path.join(AUTO_DIR, f"{sanitized_name}.json")
    schema_text = _load_recipe_schema_text()
    prompt_parts = [
        f'User asked: "{query}". No recipe matched.',
        "",
        "You are a Recipe Architect. Generate a recipe JSON that conforms to the schema below.",
        "Output the recipe JSON inside a ```json ... ``` code block.",
        "The JSON MUST conform to this schema:",
        "```json",
        schema_text if schema_text else '{"name": "...", "trigger_keywords": ["..."], "skills": [], "notes": "..."}',
        "```",
        "",
        "After the JSON block, provide a PROFESSIONAL ANSWER to the user.",
    ]
    prompt = "\n".join(prompt_parts)
    last_error = None
    result = None
    for attempt in range(1, max_retries + 1):
        print(f"[AutoCraft] Attempt {attempt}/{max_retries} for query: {query}")
        os.makedirs(AUTO_DIR, exist_ok=True)
        os.makedirs(SKILL_AUTO_DIR, exist_ok=True)
        result = _dashscope_chat([{"role": "user", "content": prompt}])
        recipe_data = _extract_json_from_response(result)
        if recipe_data is None:
            last_error = "Could not extract valid JSON from LLM response"
            print(f"[AutoCraft] {last_error} — retrying...")
            continue
        validation_errors = _validate_recipe_json(recipe_data)
        if validation_errors:
            last_error = f"Schema validation failed: {'; '.join(validation_errors)}"
            print(f"[AutoCraft] {last_error} — retrying...")
            continue
        with open(recipe_path, "w", encoding="utf-8") as f:
            json.dump(recipe_data, f, indent=2, ensure_ascii=False)
        print(f"[AutoCraft] Wrote recipe to {recipe_path}")
        # Generate .py skill files for each skill in the recipe
        skills = recipe_data.get("skills", [])
        recipe_name = recipe_data.get("name", sanitized_name)
        generated_skills = []
        for skill_name in skills:
            skill_file = _generate_skill_py(skill_name, recipe_name)
            generated_skills.append(skill_file)
        if generated_skills:
            print(f"[AutoCraft] Generated {len(generated_skills)} skill file(s): {generated_skills}")
        print(f"[AutoCraft] Recipe '{recipe_data.get('name')}' validated successfully on attempt {attempt}")
        return {
            "status": "auto_generated", "message": "已现场生成配方并执行",
            "report": result, "recipe": recipe_data.get("name", sanitized_name),
            "attempts": attempt,
        }
    print(f"[AutoCraft] FAILED after {max_retries} attempts. Last error: {last_error}")
    return {
        "status": "auto_craft_failed",
        "message": f"配方生成失败（{max_retries} 次重试后仍未通过验证）",
        "report": result or "无结果", "last_error": last_error, "attempts": max_retries,
    }
