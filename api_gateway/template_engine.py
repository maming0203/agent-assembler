"""
AutoCraft v3 Template Engine — Jinja2 based rendering

Replaces f-string hardcoded generation with proper Jinja2 templates.
Provides typed rendering functions for all recipe artifacts.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Resolve template directory relative to this module
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Create a reusable Jinja2 environment
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _get_template(name: str):
    """Get a Jinja2 template by filename."""
    return _env.get_template(name)


def render_skill_md(
    skill_name: str,
    recipe_name: str,
    trigger_keywords: list,
    version: str = "1.0.0",
    category: str = "AutoCraft",
    intent_description: str = "",
    scenario_tags: Optional[List] = None,
    target_audience: str = "",
    few_shot_examples: Optional[List] = None,
    capabilities: Optional[List] = None,
    input_schema: Optional[List] = None,
    output_schema: Optional[List] = None,
) -> str:
    """Render a SKILL.md file from Jinja2 template."""
    template = _get_template("skill_md.j2")
    return template.render(
        skill_name=skill_name,
        recipe_name=recipe_name,
        trigger_keywords=trigger_keywords,
        version=version,
        category=category,
        created_date=datetime.now().strftime("%Y-%m-%d"),
        intent_description=intent_description or f"用户需要关于{recipe_name}的专业帮助",
        scenario_tags=scenario_tags or ["咨询", "分析"],
        target_audience=target_audience or f"需要{recipe_name}解决方案的用户",
        few_shot_examples=few_shot_examples or [
            {"user": f"请帮我{recipe_name}", "assistant": "我来帮您分析..."},
            {"user": f"关于{recipe_name}的问题", "assistant": "根据您的情况..."},
        ],
        capabilities=capabilities or [
            f"分析用户关于**{recipe_name}**的需求",
            "提供专业建议和解决方案",
            "基于行业最佳实践给出操作指南",
            "运行配套 Python 脚本获取精确计算结果",
        ],
        input_schema=input_schema or [
            {"name": "query", "type": "string", "description": "用户原始问题", "required": True},
        ],
        output_schema=output_schema or [
            {"name": "status", "type": "string", "description": "执行状态: ok/error"},
            {"name": "output", "type": "string", "description": "人类可读的结果摘要"},
        ],
    )


def render_recipe_script(
    recipe_name: str,
    class_name: str,
    trigger_keywords: list,
    category: str = "AutoCraft",
    recipe_path: str = "",
) -> str:
    """Render a Python script from Jinja2 template."""
    template = _get_template("recipe_script.j2")
    return template.render(
        recipe_name=recipe_name,
        class_name=class_name,
        trigger_keywords=trigger_keywords,
        category=category,
        recipe_path=recipe_path,
        created_date=datetime.now().strftime("%Y-%m-%d"),
    )


def render_mcp_config(
    skill_name: str,
    recipe_name: str,
    trigger_keywords: list,
    script_path: str = "",
    version: str = "1.0.0",
    input_schema: Optional[List] = None,
    output_schema: Optional[List] = None,
    required_params: Optional[List] = None,
    timeout: int = 60,
    retry_count: int = 0,
) -> str:
    """Render an mcp.json config from Jinja2 template."""
    template = _get_template("mcp_config.j2")
    return template.render(
        skill_name=skill_name,
        recipe_name=recipe_name,
        trigger_keywords=trigger_keywords,
        script_path=script_path,
        version=version,
        created_date=datetime.now().strftime("%Y-%m-%d"),
        input_schema=input_schema or [
            {"name": "query", "type": "string", "description": "用户原始查询", "required": True},
        ],
        output_schema=output_schema or [
            {"name": "status", "type": "string", "description": "执行状态"},
            {"name": "data", "type": "object", "description": "计算结果"},
        ],
        required_params=required_params or ["query"],
        timeout=timeout,
        retry_count=retry_count,
    )


def render_recipe_json(
    recipe_name: str,
    trigger_keywords: list,
    script_path: str = "",
    skill_md: str = "",
    mcp_config: str = "",
    description: str = "",
    notes: str = "",
    intent_description: str = "",
    scenario_tags: Optional[List] = None,
    target_audience: str = "",
    few_shot_examples: Optional[List] = None,
    skills: Optional[List] = None,
    input_schema: Optional[List] = None,
    features: Optional[List] = None,
    tags: Optional[List] = None,
    agent_id: str = "default",
    fallback_agent: str = "general",
    priority: int = 1,
    model: str = "qwen3.6-plus",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: int = 60,
    test_passed: bool = False,
) -> str:
    """Render a recipe JSON from Jinja2 template."""
    template = _get_template("recipe_json.j2")
    return template.render(
        recipe_name=recipe_name,
        trigger_keywords=trigger_keywords,
        script_path=script_path,
        skill_md=skill_md,
        mcp_config=mcp_config,
        description=description,
        notes=notes,
        intent_description=intent_description,
        scenario_tags=scenario_tags or [],
        target_audience=target_audience,
        few_shot_examples=few_shot_examples or [],
        skills=skills or [],
        input_schema=input_schema or [],
        features=features or [],
        tags=tags or [],
        agent_id=agent_id,
        fallback_agent=fallback_agent,
        priority=priority,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        test_passed=test_passed,
        version="1.0.0",
        category="AutoCraft",
        created_date=datetime.now().strftime("%Y-%m-%d"),
    )
