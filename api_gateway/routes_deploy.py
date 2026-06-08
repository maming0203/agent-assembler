"""Deploy 端点 — 从 p5_routes.py 拆分。"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .config import SKILL_BASE
from .db import get_user_id_by_key

router = APIRouter(prefix="/api/v1", tags=["deploy"])


class DeployRequest(BaseModel):
    name: str
    description: str
    platform: str  # Coze | Qianwen

class DeployCompleteRequest(BaseModel):
    name: str
    coze_token: str
    coze_space_id: str


@router.post("/deploy/coze")
async def deploy_to_coze(req: DeployRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")
    uid = get_user_id_by_key(x_api_key)
    if not uid:
        raise HTTPException(403, "Invalid API Key")
    try:
        from agent_assembler.recipe import Recipe
        from agent_assembler.adapters import CozeAdapter
    except ImportError:
        return {"status": "error", "message": "SDK not available"}
    recipe = Recipe(name=req.name, trigger_keywords=[req.name], skills=[], notes=req.description)
    adapter = CozeAdapter(skills_dir=SKILL_BASE)
    config = adapter.export(recipe)
    bot_info = config["bot_info"]
    return {
        "status": "ready",
        "message": "Coze deployment prepared. Provide coze_token and coze_space_id to complete.",
        "bot_info": bot_info,
        "next_step": "POST /api/v1/deploy/coze/complete with {coze_token, coze_space_id}",
    }

@router.post("/deploy/coze/complete")
async def deploy_coze_complete(req: DeployCompleteRequest, x_api_key: str = Header(None)):
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
    recipe = Recipe(name=req.name, trigger_keywords=[req.name], skills=[], notes="")
    adapter = CozeAdapter(skills_dir=SKILL_BASE)
    config = adapter.export(recipe)
    bot_info = config["bot_info"]
    client = CozeApiClient(req.coze_token)
    bot_id = client.create_bot(
        name=bot_info["name"], description=bot_info["description"],
        prompt=bot_info["prompt_info"]["prompt"], space_id=req.coze_space_id,
    )
    if not bot_id:
        return {"status": "error", "message": "Bot creation failed"}
    pub_result = client.publish_bot(bot_id, 1024)
    return {"status": "published", "bot_id": bot_id, "publish_result": pub_result,
            "message": f"Bot '{req.name}' published to Coze API channel"}

@router.post("/deploy/qianwen")
async def deploy_to_qianwen(req: DeployRequest, x_api_key: str = Header(None)):
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
    recipe = Recipe(name=req.name, trigger_keywords=[req.name], skills=[], notes=req.description)
    adapter = QianwenAdapter(skills_dir=SKILL_BASE)
    config = adapter.export(recipe)
    return {"status": "ready", "message": "Qianwen deployment prepared.", "config": config}
