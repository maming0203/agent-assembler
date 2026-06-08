"""AutoCraft v2 — recipe generation, schema validation, retry logic, skill generation.

修复清单：
1. schema 路径断裂 → 改为从 api_gateway/recipe_schema.json 加载
2. 技能文件格式混用 → 统一为 .md 格式（与现有技能库一致）
3. 技能生成太薄 → 生成含业务逻辑骨架的 .md 技能文件
4. 校验不严格 → 修复 trigger_keywords / name / skills 校验
"""
import json
import os
import re
from typing import Optional

from .config import (
    AUTO_DIR, SKILL_AUTO_DIR,
    RECIPE_SCHEMA_PATH,
)

os.makedirs(AUTO_DIR, exist_ok=True)
os.makedirs(SKILL_AUTO_DIR, exist_ok=True)


def _load_recipe_schema_text() -> str:
    """Load recipe schema JSON text for embedding in LLM prompts.
    
    修复：直接使用 api_gateway/recipe_schema.json（config.py 中已定义路径）。
    """
    try:
        with open(RECIPE_SCHEMA_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[AutoCraft] WARN: Could not load schema from {RECIPE_SCHEMA_PATH}: {e}")
        # fallback: 内联最小 schema
        return json.dumps({
            "name": "配方名称（必填，不能为空）",
            "trigger_keywords": ["触发关键词1", "触发关键词2"],  # 至少2个
            "skills": [],  # 技能名称数组
            "notes": "配方说明"
        }, ensure_ascii=False, indent=2)


def _validate_recipe_json(data: dict) -> list:
    """校验配方 JSON。
    
    修复：强化 trigger_keywords 和 name 校验。
    """
    errors: list[str] = []
    
    # name 必填，不能为空
    if "name" not in data:
        errors.append("Missing required field: 'name'")
    elif not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("'name' must be a non-empty string")
    
    # trigger_keywords 必填，至少 2 个
    if "trigger_keywords" not in data:
        errors.append("Missing required field: 'trigger_keywords'")
    elif not isinstance(data["trigger_keywords"], list):
        errors.append("'trigger_keywords' must be a list")
    elif len(data["trigger_keywords"]) < 2:
        errors.append("'trigger_keywords' must have at least 2 keywords")
    elif not all(isinstance(kw, str) and kw.strip() for kw in data["trigger_keywords"]):
        errors.append("All items in 'trigger_keywords' must be non-empty strings")
    
    # skills 必须是字符串数组
    if "skills" in data:
        if not isinstance(data["skills"], list):
            errors.append("'skills' must be a list")
        else:
            # 修复：只接受纯字符串，不接受字典/路径
            for i, s in enumerate(data["skills"]):
                if not isinstance(s, str):
                    errors.append(f"skills[{i}] must be a string, got {type(s).__name__}")
    
    # notes 必须是字符串
    if "notes" in data and not isinstance(data["notes"], str):
        errors.append("'notes' must be a string")
    
    # routing 必须是对象
    if "routing" in data and not isinstance(data["routing"], dict):
        errors.append("'routing' must be an object")
    
    # engine_config 必须是对象
    if "engine_config" in data and not isinstance(data["engine_config"], dict):
        errors.append("'engine_config' must be an object")
    
    return errors


def _extract_json_from_response(text: str):
    """Extract JSON from LLM response."""
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
    
    # Try bare JSON
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
    return re.sub(r"[^\w\u4e00-\u9fa5]", "_", q)[:30]


def _generate_skill_md(skill_name: str, recipe_name: str, recipe_keywords: list[str]) -> str:
    """生成 .md 技能文件（含业务逻辑骨架）。
    
    修复：从 .py 改为 .md，内容与 recipe 关联，包含角色定义和工作流程。
    """
    skill_content = f"""---
name: {skill_name}
recipe: {recipe_name}
version: 1.0
---

# {skill_name}

> 自动生成技能文件 — 由 AutoCraft 为配方「{recipe_name}」创建

## 触发关键词
{', '.join(recipe_keywords)}

## 角色定义
你是一位专注于**{recipe_name}**领域的专家。

## 能力
- 分析用户关于**{recipe_name}**的需求
- 提供专业建议和解决方案
- 基于行业最佳实践给出操作指南

## 工作流程
1. **理解需求** — 明确用户的具体问题和背景
2. **分析场景** — 识别关键因素和约束条件
3. **提供方案** — 给出结构化、可操作的建议
4. **跟进反馈** — 根据用户反馈调整方案

## 输出格式
- 使用 Markdown 格式
- 先给结论，再给详细分析
- 提供具体的操作步骤
- 注明假设条件和注意事项

## 约束
- 不提供违法、违规、有害的建议
- 不确定时明确告知用户
- 涉及数据/计算时注明假设条件
"""
    
    skill_file = os.path.join(SKILL_AUTO_DIR, f"{skill_name}.md")
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(skill_content)
    
    print(f"[AutoCraft] Skill '{skill_name}' generated as .md: {skill_file}")
    return skill_file


async def auto_craft_and_run(query, user_id, max_retries: int = 3):
    """Auto-generate a recipe + skill when no existing recipe matches.
    
    修复：
    - 使用正确的 schema 路径
    - 强化校验逻辑
    - 生成 .md 技能文件
    - 自动补全缺失字段
    """
    sanitized_name = sanitize(query)
    recipe_path = os.path.join(AUTO_DIR, f"{sanitized_name}.json")
    
    schema_text = _load_recipe_schema_text()
    
    prompt_parts = [
        f'User asked: "{query}". No recipe matched.',
        '',
        'You are a Recipe Architect. Generate a recipe JSON that conforms to the schema below.',
        'Output ONLY the recipe JSON inside a ```json ... ``` code block. No other text.',
        '',
        'Schema:',
        '```json',
        schema_text if schema_text else '{"name": "...", "trigger_keywords": ["..."], "skills": [], "notes": "..."}',
        '```',
        '',
        'IMPORTANT:',
        '- "name" must be a concise recipe name (not the user query itself)',
        '- "trigger_keywords" MUST have at least 2 relevant keywords',
        '- "skills" MUST be an array of strings (skill names only, no objects/paths)',
        '- "notes" should be a helpful description of what this recipe does',
        '',
        'After the JSON block, provide a PROFESSIONAL ANSWER to the user.',
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
        
        # 校验
        validation_errors = _validate_recipe_json(recipe_data)
        if validation_errors:
            # 尝试自动修复
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
                # 修复后重新校验
                validation_errors = _validate_recipe_json(recipe_data)
                if not validation_errors:
                    print(f"[AutoCraft] Auto-fixed recipe on attempt {attempt}")
                else:
                    last_error = f"Schema validation failed (even after auto-fix): {'; '.join(validation_errors)}"
                    print(f"[AutoCraft] {last_error} — retrying...")
                    continue
            else:
                last_error = f"Schema validation failed: {'; '.join(validation_errors)}"
                print(f"[AutoCraft] {last_error} — retrying...")
                continue
        
        # 规范化 skills（只保留字符串）
        skills = []
        for s in recipe_data.get("skills", []):
            if isinstance(s, str):
                skills.append(s)
        recipe_data["skills"] = skills
        
        # 落盘
        with open(recipe_path, "w", encoding="utf-8") as f:
            json.dump(recipe_data, f, indent=2, ensure_ascii=False)
        print(f"[AutoCraft] Wrote recipe to {recipe_path}")
        
        # 生成 .md 技能文件
        recipe_name = recipe_data.get("name", sanitized_name)
        recipe_keywords = recipe_data.get("trigger_keywords", [])
        generated_skills = []
        
        for skill_name in skills:
            skill_file = _generate_skill_md(skill_name, recipe_name, recipe_keywords)
            generated_skills.append(skill_file)
        
        if generated_skills:
            print(f"[AutoCraft] Generated {len(generated_skills)} skill file(s)")
        
        print(f"[AutoCraft] Recipe '{recipe_name}' validated successfully on attempt {attempt}")
        return {
            "status": "auto_generated",
            "message": "已现场生成配方（脚本执行需手动部署）",
            "report": result,
            "recipe": recipe_name,
            "recipe_path": recipe_path,
            "skills_generated": generated_skills,
            "attempts": attempt,
        }
    
    print(f"[AutoCraft] FAILED after {max_retries} attempts. Last error: {last_error}")
    return {
        "status": "auto_craft_failed",
        "message": f"配方生成失败（{max_retries} 次重试后仍未通过校验）",
        "report": result or "无结果",
        "last_error": last_error,
        "attempts": max_retries,
    }
