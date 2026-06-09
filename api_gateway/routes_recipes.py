"""Recipe CRUD 端点 — 从 p5_routes.py 拆分。"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .config import RECIPE_BASE
from .db import get_user_id_by_key

router = APIRouter(prefix="/api/v1", tags=["recipes"])


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


def _load_recipes() -> list[dict[str, Any]]:
    """只加载各业务目录下的 flat JSON，不递归子子目录。
    
    跳过子目录（如 cost-accounting-sop-v1/）里的 manifest.json、pot.json、schema.json
    等技术定义文件，只返回用户配方。
    """
    recipes = []
    if not os.path.exists(RECIPE_BASE):
        return recipes

    # 排除系统目录
    EXCLUDE_DIRS = {'AutoCreated', 'scripts', 'schemas', 'autocraft', 'mined'}
    # 系统文件（不是 recipe）
    SYSTEM_FILES = {'pot.json', 'schema.json', 'index.json', 'recipe.json'}

    # 只遍历顶层目录（Finance/, Merchants/ 等）
    for top_dir in os.listdir(RECIPE_BASE):
        top_path = os.path.join(RECIPE_BASE, top_dir)
        if not os.path.isdir(top_path):
            continue
        if top_dir in EXCLUDE_DIRS:
            continue

        # 在顶层目录下只加载 flat JSON，不进入子子目录
        for f in os.listdir(top_path):
            filepath = os.path.join(top_path, f)
            # 只加载文件，不加载子目录
            if not os.path.isfile(filepath):
                continue
            if not f.endswith(".json"):
                continue
            if f in SYSTEM_FILES:
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                data["_name"] = data.get("name", f.replace(".json", ""))
                # 平格式 recipe 可能用 triggers 而非 trigger_keywords
                if "trigger_keywords" not in data and "triggers" in data:
                    data["trigger_keywords"] = data.pop("triggers")
                data["_file"] = f
                data["_path"] = filepath
                data["_category"] = top_dir
                data["_is_premium"] = "Premium" in top_dir
                recipes.append(data)
            except Exception:
                continue

    return recipes

def _find_recipe_file(name: str) -> Optional[str]:
    name_lower = name.lower()
    EXCLUDE_DIRS = {'AutoCreated', 'scripts', 'schemas', 'autocraft', 'mined'}
    SYSTEM_FILES = {'pot.json', 'schema.json', 'index.json', 'recipe.json'}

    for top_dir in os.listdir(RECIPE_BASE):
        top_path = os.path.join(RECIPE_BASE, top_dir)
        if not os.path.isdir(top_path) or top_dir in EXCLUDE_DIRS:
            continue
        for f in os.listdir(top_path):
            filepath = os.path.join(top_path, f)
            if not os.path.isfile(filepath) or not f.endswith(".json") or f in SYSTEM_FILES:
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                rname = (data.get("name") or "").lower()
                if name_lower in rname or rname in name_lower or name_lower in f.lower() or f.lower() in name_lower:
                    return filepath
            except Exception:
                continue
    return None


@router.get("/recipes")
async def list_recipes(x_api_key: str = Header(None)):
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")
    recipes = _load_recipes()
    return {
        "total": len(recipes),
        "categories": list(set(r.get("_category", "") for r in recipes)),
        "recipes": [
            {"name": r.get("_name") or r.get("name", "Unknown"),
             "keywords": r.get("trigger_keywords", []),
             "skills": r.get("skills", []),
             "notes": r.get("notes", ""),
             "file": r.get("_file", ""),
             "category": r.get("_category", ""),
             "is_premium": r.get("_is_premium", False)}
            for r in recipes
        ],
    }

@router.get("/recipes/search")
async def search_recipes(q: str, x_api_key: str = Header(None)):
    recipes = _load_recipes()
    q_lower = q.lower()
    matches = []
    for r in recipes:
        keywords = [k.lower() for k in r.get("trigger_keywords", [])]
        name = (r.get("_name") or r.get("name", "")).lower()
        notes = r.get("notes", "").lower()
        if q_lower in name or any(q_lower in k for k in keywords) or q_lower in notes:
            matches.append({"name": r.get("_name") or r.get("name"),
                           "keywords": r.get("trigger_keywords", []),
                           "notes": r.get("notes", ""),
                           "file": r.get("_file", ""),
                           "category": r.get("_category", "")})
    return {"query": q, "matches": len(matches), "recipes": matches}

@router.get("/recipes/{recipe_name}")
async def get_recipe(recipe_name: str, x_api_key: str = Header(None)):
    path = _find_recipe_file(recipe_name)
    if not path:
        raise HTTPException(404, f"Recipe not found: {recipe_name}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data

@router.post("/recipes", status_code=201)
async def create_recipe(req: RecipeCreate, x_api_key: str = Header(None)):
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")
    if _find_recipe_file(req.name):
        raise HTTPException(409, f"Recipe already exists: {req.name}")
    data = {"name": req.name, "trigger_keywords": req.trigger_keywords,
            "skills": req.skills, "notes": req.notes}
    if req.routing:
        data["routing"] = req.routing
    if req.script_path:
        data["script_path"] = req.script_path
    safe_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', req.name)
    filename = f"{safe_name}.json"
    os.makedirs(RECIPE_BASE, exist_ok=True)
    path = os.path.join(RECIPE_BASE, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return {"status": "created", "name": req.name, "path": path}

@router.put("/recipes/{recipe_name}")
async def update_recipe(recipe_name: str, req: RecipeUpdate, x_api_key: str = Header(None)):
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")
    path = _find_recipe_file(recipe_name)
    if not path:
        raise HTTPException(404, f"Recipe not found: {recipe_name}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    for field in ("name", "trigger_keywords", "skills", "notes", "routing", "script_path"):
        val = getattr(req, field, None)
        if val is not None:
            data[field] = val
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return {"status": "updated", "name": data.get("name")}

@router.delete("/recipes/{recipe_name}")
async def delete_recipe(recipe_name: str, x_api_key: str = Header(None)):
    if x_api_key:
        uid = get_user_id_by_key(x_api_key)
        if not uid:
            raise HTTPException(403, "Invalid API Key")
    path = _find_recipe_file(recipe_name)
    if not path:
        raise HTTPException(404, f"Recipe not found: {recipe_name}")
    os.remove(path)
    return {"status": "deleted", "name": recipe_name}
