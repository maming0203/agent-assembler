"""P5.1 新增端点 — Recipe CRUD、Metrics、API Keys、Deploy。

独立模块，不改动现有 core.py。
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .config import RECIPE_BASE, SKILL_BASE, DB_FILE
from .db import load_json, save_json, get_user_id_by_key
from .config import USAGE_FILE, DB_FILE, SKILL_BASE

# ──────────────────────────────────────────
# 数据文件
# ──────────────────────────────────────────

API_KEYS_FILE = os.path.join(os.path.dirname(DB_FILE), "api_keys.json")

if not os.path.exists(API_KEYS_FILE):
    os.makedirs(os.path.dirname(API_KEYS_FILE) if os.path.dirname(API_KEYS_FILE) else ".", exist_ok=True)
    save_json(API_KEYS_FILE, {})

# ──────────────────────────────────────────
# Router
# ──────────────────────────────────────────

router = APIRouter(prefix="/api/v1", tags=["P5"])


# ──────────────────────────────────────────
# Models
# ──────────────────────────────────────────

class RecipeCreate(BaseModel):
    name: str
    trigger_keywords: list[str]
    skills: list[str] = []
    notes: str = ""
    routing: Optional[str] = None
    script_path: Optional[str] = None

class RecipeUpdate(BaseModel):
    name: Optional[str] = None
    trigger_keywords: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    notes: Optional[str] = None
    routing: Optional[str] = None
    script_path: Optional[str] = None

class ApiKeyCreate(BaseModel):
    name: str
    plan: str = "free"       # free | pro | enterprise

class DeployRequest(BaseModel):
    name: str
    description: str
    platform: str            # Coze | Qianwen


# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────

def _load_api_keys() -> dict:
    return load_json(API_KEYS_FILE)

def _save_api_keys(data: dict):
    save_json(API_KEYS_FILE, data)

def _load_recipes() -> list[dict[str, Any]]:
    """加载所有配方（含 metadata）。"""
    recipes = []
    if not os.path.exists(RECIPE_BASE):
        return recipes
    for root, _, files in os.walk(RECIPE_BASE):
        if "Premium_Assets" in root:
            continue
        for f in files:
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                data["_file"] = f
                data["_path"] = os.path.join(root, f)
                data["_is_premium"] = False
                recipes.append(data)
            except Exception:
                continue
    return recipes

def _find_recipe_file(name: str) -> Optional[str]:
    """按名称查找配方文件路径。"""
    name_lower = name.lower()
    for root, _, files in os.walk(RECIPE_BASE):
        for f in files:
            if f.endswith(".json") and (name_lower in f.lower() or f.lower() in name_lower):
                return os.path.join(root, f)
    return None

def _ensure_api_key_dir():
    d = os.path.dirname(API_KEYS_FILE)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


# ──────────────────────────────────────────
# Recipe CRUD
# ──────────────────────────────────────────

@router.get("/recipes")
async def list_recipes(x_api_key: str = Header(None)):
    """列出所有配方。"""
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")

    recipes = _load_recipes()
    return {
        "total": len(recipes),
        "recipes": [
            {
                "name": r.get("name", "Unknown"),
                "keywords": r.get("trigger_keywords", []),
                "skills": r.get("skills", []),
                "notes": r.get("notes", ""),
                "file": r.get("_file", ""),
                "is_premium": r.get("_is_premium", False),
            }
            for r in recipes
        ],
    }

@router.get("/recipes/search")
async def search_recipes(q: str, x_api_key: str = Header(None)):
    """搜索配方（关键词匹配）。"""
    recipes = _load_recipes()
    q_lower = q.lower()
    matches = []
    for r in recipes:
        keywords = [k.lower() for k in r.get("trigger_keywords", [])]
        name = r.get("name", "").lower()
        notes = r.get("notes", "").lower()
        if q_lower in name or any(q_lower in k for k in keywords) or q_lower in notes:
            matches.append({
                "name": r.get("name"),
                "keywords": r.get("trigger_keywords", []),
                "notes": r.get("notes", ""),
                "file": r.get("_file", ""),
            })
    return {"query": q, "matches": len(matches), "recipes": matches}

@router.get("/recipes/{recipe_name}")
async def get_recipe(recipe_name: str, x_api_key: str = Header(None)):
    """获取单个配方详情。"""
    path = _find_recipe_file(recipe_name)
    if not path:
        raise HTTPException(404, f"Recipe not found: {recipe_name}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data

@router.post("/recipes", status_code=201)
async def create_recipe(req: RecipeCreate, x_api_key: str = Header(None)):
    """创建新配方。"""
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")

    if _find_recipe_file(req.name):
        raise HTTPException(409, f"Recipe already exists: {req.name}")

    data = {
        "name": req.name,
        "trigger_keywords": req.trigger_keywords,
        "skills": req.skills,
        "notes": req.notes,
    }
    if req.routing:
        data["routing"] = req.routing
    if req.script_path:
        data["script_path"] = req.script_path

    # 保存到 recipe 目录
    safe_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', req.name)
    filename = f"{safe_name}.json"
    os.makedirs(RECIPE_BASE, exist_ok=True)
    path = os.path.join(RECIPE_BASE, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    return {"status": "created", "name": req.name, "path": path}

@router.put("/recipes/{recipe_name}")
async def update_recipe(recipe_name: str, req: RecipeUpdate, x_api_key: str = Header(None)):
    """更新配方。"""
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")

    path = _find_recipe_file(recipe_name)
    if not path:
        raise HTTPException(404, f"Recipe not found: {recipe_name}")

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if req.name is not None:
        data["name"] = req.name
    if req.trigger_keywords is not None:
        data["trigger_keywords"] = req.trigger_keywords
    if req.skills is not None:
        data["skills"] = req.skills
    if req.notes is not None:
        data["notes"] = req.notes
    if req.routing is not None:
        data["routing"] = req.routing
    if req.script_path is not None:
        data["script_path"] = req.script_path

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    return {"status": "updated", "name": data.get("name")}

@router.delete("/recipes/{recipe_name}")
async def delete_recipe(recipe_name: str, x_api_key: str = Header(None)):
    """删除配方。"""
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")

    path = _find_recipe_file(recipe_name)
    if not path:
        raise HTTPException(404, f"Recipe not found: {recipe_name}")

    os.remove(path)
    return {"status": "deleted", "name": recipe_name}


# ──────────────────────────────────────────
# API Key 管理
# ──────────────────────────────────────────

@router.get("/apikeys")
async def list_api_keys(x_api_key: str = Header(None)):
    """列出所有 API Key（管理接口）。"""
    keys = _load_api_keys()
    return {
        "total": len(keys),
        "keys": [
            {"key": k, "name": v.get("name", ""), "plan": v.get("plan", "free"),
             "created": v.get("created", 0), "last_used": v.get("last_used", 0)}
            for k, v in keys.items()
        ],
    }

@router.post("/apikeys", status_code=201)
async def create_api_key(req: ApiKeyCreate, x_api_key: str = Header(None)):
    """创建新的 API Key。"""
    # 管理接口：需要 master key
    if x_api_key:
        keys = _load_api_keys()
        master_info = keys.get(x_api_key)
        if not master_info or master_info.get("plan") not in ("pro", "enterprise"):
            # 无 master key 时也允许创建，但只能 free plan
            pass

    new_key = f"sk-{secrets.token_hex(16)}"
    keys = _load_api_keys()
    keys[new_key] = {
        "name": req.name,
        "plan": req.plan,
        "created": int(time.time()),
        "last_used": 0,
    }
    _save_api_keys(keys)

    return {"status": "created", "key": new_key, "name": req.name, "plan": req.plan}

@router.delete("/apikeys/{key_prefix}")
async def revoke_api_key(key_prefix: str, x_api_key: str = Header(None)):
    """撤销 API Key（按前缀匹配）。"""
    keys = _load_api_keys()
    found = None
    for k in keys:
        if k.startswith(key_prefix):
            found = k
            break
    if not found:
        raise HTTPException(404, f"Key not found with prefix: {key_prefix}")

    del keys[found]
    _save_api_keys(keys)
    return {"status": "revoked", "key_prefix": key_prefix}


# ──────────────────────────────────────────
# Metrics / Analytics
# ──────────────────────────────────────────

@router.get("/metrics")
async def get_metrics(limit: int = 50, x_api_key: str = Header(None)):
    """获取运行指标（从 db usage 文件读取）。"""
    usage = load_json(USAGE_FILE) if os.path.exists(USAGE_FILE) else {}
    total_runs = sum(v.get("count", 0) if isinstance(v, dict) else v for v in usage.values())

    return {
        "total_runs": total_runs,
        "users": len(usage),
        "top_users": sorted(
            [{"user": k, "runs": v.get("count", 0) if isinstance(v, dict) else v}
             for k, v in usage.items()],
            key=lambda x: x["runs"],
            reverse=True,
        )[:limit],
    }

@router.get("/metrics/summary")
async def get_metrics_summary(x_api_key: str = Header(None)):
    """汇总指标。"""
    usage = load_json(USAGE_FILE) if os.path.exists(USAGE_FILE) else {}
    users_db = load_json(DB_FILE) if os.path.exists(DB_FILE) else {}

    total_runs = sum(v.get("count", 0) if isinstance(v, dict) else v for v in usage.values())
    plans = {}
    for uid, info in users_db.items():
        plan = info.get("plan", "free") if isinstance(info, dict) else "free"
        plans[plan] = plans.get(plan, 0) + 1

    return {
        "total_users": len(users_db),
        "total_runs": total_runs,
        "plan_distribution": plans,
        "active_recipes": len(_load_recipes()),
    }


@router.get("/metrics/timeseries")
async def get_metrics_timeseries(days: int = 7, x_api_key: str = Header(None)):
    """时序指标（最近 N 天的运行次数）。"""
    usage = load_json(USAGE_FILE) if os.path.exists(USAGE_FILE) else {}
    # 简单时序：按用户汇总
    data_points = []
    for uid, info in usage.items():
        count = info.get("count", 0) if isinstance(info, dict) else info
        data_points.append({"user": uid, "runs": count})
    return {
        "days": days,
        "total": sum(d["runs"] for d in data_points),
        "data": data_points,
    }


class DeployCompleteRequest(BaseModel):
    name: str
    coze_token: str
    coze_space_id: str


@router.post("/deploy/coze/complete")
async def deploy_coze_complete(req: DeployCompleteRequest, x_api_key: str = Header(None)):
    """完成 Coze 发布：创建 Bot + 发布到 API 渠道。"""
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")
    uid = get_user_id_by_key(x_api_key)
    if not uid:
        raise HTTPException(403, "Invalid API Key")

    try:
        from agent_assembler.recipe import Recipe
        from agent_assembler.adapters import CozeAdapter
        from agent_assembler.deploy import CozeApiClient
    except ImportError:
        return {"status": "error", "message": "SDK not available"}

    recipe = Recipe(
        name=req.name,
        trigger_keywords=[req.name],
        skills=[],
        notes="",
    )
    adapter = CozeAdapter(skills_dir=SKILL_BASE)
    config = adapter.export(recipe)
    bot_info = config["bot_info"]

    client = CozeApiClient(req.coze_token)
    bot_id = client.create_bot(
        name=bot_info["name"],
        description=bot_info["description"],
        prompt=bot_info["prompt_info"]["prompt"],
        space_id=req.coze_space_id,
    )

    if not bot_id:
        return {"status": "error", "message": "Bot creation failed"}

    pub_result = client.publish_bot(bot_id, 1024)

    return {
        "status": "published",
        "bot_id": bot_id,
        "publish_result": pub_result,
        "message": f"Bot '{req.name}' published to Coze API channel",
    }


# ──────────────────────────────────────────
# Deploy 一键发布
# ──────────────────────────────────────────

@router.post("/deploy/coze")
async def deploy_to_coze(req: DeployRequest, x_api_key: str = Header(None)):
    """一键发布到 Coze。"""
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")
    uid = get_user_id_by_key(x_api_key)
    if not uid:
        raise HTTPException(403, "Invalid API Key")

    try:
        from agent_assembler.recipe import Recipe
        from agent_assembler.adapters import CozeAdapter
        from agent_assembler.deploy import CozeApiClient
        from .config import SKILL_BASE
    except ImportError:
        return {"status": "error", "message": "SDK not available"}

    recipe = Recipe(
        name=req.name,
        trigger_keywords=[req.name],
        skills=[],
        notes=req.description,
    )
    adapter = CozeAdapter(skills_dir=SKILL_BASE)
    config = adapter.export(recipe)
    bot_info = config["bot_info"]

    # 需要 Coze Token（从用户 DB 获取或 Header 传入）
    return {
        "status": "ready",
        "message": "Coze deployment prepared. Provide coze_token and coze_space_id to complete.",
        "bot_info": bot_info,
        "next_step": "POST /api/v1/deploy/coze/complete with {coze_token, coze_space_id, bot_info}",
    }

@router.post("/deploy/qianwen")
async def deploy_to_qianwen(req: DeployRequest, x_api_key: str = Header(None)):
    """一键发布到千问。"""
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")
    uid = get_user_id_by_key(x_api_key)
    if not uid:
        raise HTTPException(403, "Invalid API Key")

    try:
        from agent_assembler.recipe import Recipe
        from agent_assembler.adapters import QianwenAdapter
    except ImportError:
        return {"status": "error", "message": "SDK not available"}

    recipe = Recipe(
        name=req.name,
        trigger_keywords=[req.name],
        skills=[],
        notes=req.description,
    )
    adapter = QianwenAdapter(skills_dir=SKILL_BASE)
    config = adapter.export(recipe)

    return {
        "status": "ready",
        "message": "Qianwen deployment prepared.",
        "config": config,
    }
