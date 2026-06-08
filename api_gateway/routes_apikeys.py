"""API Key 管理端点 — 从 p5_routes.py 拆分。"""
from __future__ import annotations

import os
import secrets
import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .db import load_json, save_json

router = APIRouter(prefix="/api/v1", tags=["apikeys"])

API_KEYS_FILE = os.path.join(os.path.dirname(__file__), "../data/api_keys.json")
API_KEYS_FILE = os.path.normpath(API_KEYS_FILE)

if not os.path.exists(API_KEYS_FILE):
    os.makedirs(os.path.dirname(API_KEYS_FILE) if os.path.dirname(API_KEYS_FILE) else ".", exist_ok=True)
    save_json(API_KEYS_FILE, {})


class ApiKeyCreate(BaseModel):
    name: str
    plan: str = "free"  # free | pro | enterprise


def _load_api_keys() -> dict:
    return load_json(API_KEYS_FILE)

def _save_api_keys(data: dict):
    save_json(API_KEYS_FILE, data)


@router.get("/apikeys")
async def list_api_keys(x_api_key: str = Header(None)):
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
    if x_api_key:
        keys = _load_api_keys()
        master_info = keys.get(x_api_key)
        if not master_info or master_info.get("plan") not in ("pro", "enterprise"):
            pass
    new_key = f"sk-{secrets.token_hex(16)}"
    keys = _load_api_keys()
    keys[new_key] = {"name": req.name, "plan": req.plan, "created": int(time.time()), "last_used": 0}
    _save_api_keys(keys)
    return {"status": "created", "key": new_key, "name": req.name, "plan": req.plan}

@router.delete("/apikeys/{key_prefix}")
async def revoke_api_key(key_prefix: str, x_api_key: str = Header(None)):
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
