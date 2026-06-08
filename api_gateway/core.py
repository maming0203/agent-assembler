"""Core Gateway module — FastAPI app, routes, DB ops, recipe matching, usage tracking."""
import json
import os
import shlex
import subprocess
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from .autocraft import auto_craft_and_run, sanitize
from .config import (
    AUTO_DIR, DISPATCHER_SCRIPT, INGESTOR_SCRIPT, IS_CLOUD,
    MANIFESTS_DIR, RECIPE_BASE, ROUTING_SCHEMA_PATH, SKILL_BASE,
    SKILL_AUTO_DIR, UPLOAD_DIR, DB_FILE, USAGE_FILE,
    AUTOCRAFT_REF_DIR, RECIPE_SCHEMA_PATH, SCRIPT_DIRS,
)
from .db import (
    check_usage, find_recipe, find_skill_in_directory,
    get_user_id_by_key, increment_usage, is_premium,
    load_json, load_skill, paywall_response, save_json,
)
from .multimodal import handle_upload, _ingestor_extract_keywords, _create_dispatcher
from .script_engine import _extract_script_args, _run_script

# App
app = FastAPI(title="Agent Assembler Gateway", version="2.1.0")

# P5 Routes
from .p5_routes import router as p5_router
app.include_router(p5_router)

# Session
SESSIONS = {}

# Models
class QueryRequest(BaseModel):
    query: str

class AgentExportRequest(BaseModel):
    name: str
    description: str
    platform: str

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    file_path: Optional[str] = None

class LoginResponse(BaseModel):
    status: str
    api_key: str
    user_id: str

# SDK import
try:
    from agent_assembler import Assembler
    from agent_assembler.adapters import CozeAdapter, QianwenAdapter
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


def _load_agent_system_prompt(agent_id: str) -> str:
    if not agent_id or not os.path.exists(MANIFESTS_DIR):
        return ""
    for f in os.listdir(MANIFESTS_DIR):
        if not f.endswith(".json"):
            continue
        filepath = os.path.join(MANIFESTS_DIR, f)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("id") == agent_id or f.replace(".json", "") == agent_id:
                return data.get("system_prompt", data.get("description", ""))
        except Exception:
            continue
    return ""


def _call_llm(messages: list) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "") or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        return "LLM API key not configured."
    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model = os.environ.get("CHAT_MODEL_NAME", os.environ.get("MODEL_NAME", "qwen-plus"))
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=api_base)
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=0.7, max_tokens=2048,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"LLM call failed: {str(e)}"


def call_agent(agent_id, msg):
    try:
        safe_msg = shlex.quote(msg)
        cmd_str = f"openclaw agent --agent {agent_id} --message {safe_msg} --json --timeout 120"
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=130)
        stdout = res.stdout
        if "{" in stdout:
            json_str = stdout[stdout.find("{"):]
            try:
                data = json.loads(json_str)
                payloads = data.get("result", {}).get("payloads", [])
                if payloads and "text" in payloads[0]:
                    return payloads[0]["text"]
            except json.JSONDecodeError:
                pass
        err_msg = res.stderr.strip()[:200] if res.stderr else "Unknown error"
        return f"执行失败: {err_msg}"
    except Exception as e:
        return f"超时或错误: {str(e)}"


# Routes
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "2.1.0"}


@app.get("/api/v1/login", response_model=LoginResponse)
async def login(device_id: str = "test_device"):
    db = load_json(DB_FILE)
    if device_id not in db or isinstance(db[device_id], str):
        db[device_id] = {"api_key": f"key_{device_id}_{int(time.time())}", "plan": "free"}
        save_json(DB_FILE, db)
    return {"status": "success", "api_key": db[device_id]["api_key"], "user_id": device_id}


@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...), file_type: str = Form(None)):
    return await handle_upload(file, file_type)


@app.get("/api/v1/agents")
async def list_agents():
    agents = []
    if not os.path.exists(MANIFESTS_DIR):
        return {"agents": []}
    for f in os.listdir(MANIFESTS_DIR):
        if not f.endswith(".json"):
            continue
        filepath = os.path.join(MANIFESTS_DIR, f)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            agents.append({
                "id": data.get("id", f.replace(".json", "")),
                "name": data.get("name", "Unknown Agent"),
                "description": data.get("description", ""),
                "tags": data.get("tags", []),
            })
        except Exception:
            continue
    agents.sort(key=lambda a: a["name"])
    return {"agents": agents}


@app.post("/api/v1/chat")
async def chat(req: ChatRequest):
    user_input = req.message.strip()
    if not user_input:
        return {"status": "error", "message": "消息不能为空"}
    extracted = _ingestor_extract_keywords(user_input)
    keywords = extracted.get("keywords", [])
    intent = extracted.get("intent", "未知")
    topics = extracted.get("topics", [])
    routing_result = {"status": "unmatched", "message": "未找到匹配的 Agent"}
    agent_name = None
    dispatcher = _create_dispatcher()
    if dispatcher is not None:
        try:
            routing_result = dispatcher.route(keywords)
        except Exception as e:
            routing_result = {"status": "error", "message": f"Dispatcher 路由失败: {str(e)}"}
    if routing_result.get("status") == "routed":
        agent = routing_result.get("agent", {})
        agent_name = agent.get("name", "Unknown")
        agent_id = agent.get("id", "unknown")
        score = routing_result.get("score", 0)
        system_prompt = agent.get("system_prompt", agent.get("description", ""))
        print(f"[Dispatcher] Routing to: {agent_name} (score: {score})")
        if req.session_id:
            history = SESSIONS.get(req.session_id, [])
            manifest_prompt = _load_agent_system_prompt(req.agent_id or agent_id)
            if not manifest_prompt:
                manifest_prompt = system_prompt
            messages = []
            if manifest_prompt:
                messages.append({"role": "system", "content": manifest_prompt})
            messages.extend(history)
            messages.append({"role": "user", "content": user_input})
            llm_response = _call_llm(messages)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": llm_response})
            if len(history) > 20:
                history = history[-20:]
            SESSIONS[req.session_id] = history
            return {
                "status": "success", "session_id": req.session_id, "message": llm_response,
                "agent": {"name": agent_name, "id": agent_id,
                          "description": agent.get("description", ""), "tags": agent.get("tags", [])},
                "history_length": len(history), "routing_score": score,
                "extracted": {"keywords": keywords, "intent": intent, "topics": topics},
            }
        return {
            "status": "success", "message": f"已为您路由到 {agent_name}",
            "agent": {"name": agent_name, "id": agent_id,
                      "description": agent.get("description", ""), "tags": agent.get("tags", [])},
            "system_prompt": system_prompt, "routing_score": score,
            "extracted": {"keywords": keywords, "intent": intent, "topics": topics},
        }
    elif routing_result.get("status") == "conflict":
        candidates = routing_result.get("candidates", [])
        candidate_names = [c.get("name", "Unknown") for c in candidates]
        return {
            "status": "conflict", "message": "多个 Agent 匹配: " + ", ".join(candidate_names),
            "candidates": candidate_names,
            "extracted": {"keywords": keywords, "intent": intent, "topics": topics},
        }
    else:
        return {
            "status": "unmatched", "message": "暂未找到匹配的 Agent，已为您记录需求",
            "extracted": {"keywords": keywords, "intent": intent, "topics": topics},
        }


@app.post("/api/v1/run")
async def run_recipe(req: QueryRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")
    user_id = get_user_id_by_key(x_api_key)
    if not user_id:
        raise HTTPException(403, "Invalid Key")
    db = load_json(DB_FILE)
    user_info = db.get(user_id, {})
    user_plan = user_info.get("plan", "free") if isinstance(user_info, dict) else "free"
    recipe = find_recipe(req.query)
    if not recipe:
        return await auto_craft_and_run(req.query, user_id)
    if is_premium(recipe) and user_plan == "free":
        return paywall_response("Premium 配方需要升级解锁。")
    if user_plan == "free":
        if check_usage(user_id) >= 3:
            return paywall_response("今日免费额度已用完。")
    increment_usage(user_id)
    script_path = recipe.get("script_path") or recipe.get("script") or recipe.get("code")
    if script_path:
        script_args = _extract_script_args(recipe, req.query)
        success, script_output = _run_script(script_path, script_args)
        if success:
            skill_content = load_skill(recipe)
            agent_query = (
                f"You are an assistant. A calculation/processing tool has produced the following result.\n"
                f"Strictly follow this skill logic for context:\n{skill_content}\n\n"
                f"TOOL OUTPUT:\n{script_output}\n\n"
                f"User Query: {req.query}\n\n"
                f"Explain this result to the user in a clear, professional manner. "
                f"Do NOT recalculate."
            )
        else:
            print(f"[Script Engine] Script failed, falling back to LLM: {script_output}")
            skill_content = load_skill(recipe)
            agent_query = (
                f"Strictly follow this skill logic:\n{skill_content}\n\n"
                f"User Query: {req.query}\n\n"
                f"Note: Script failed: {script_output}. Please answer using your knowledge."
            )
    else:
        skill_content = load_skill(recipe)
        agent_query = f"Strictly follow this skill logic:\n{skill_content}\n\nUser Query: {req.query}"
    routing_id = recipe.get("routing")
    if not routing_id:
        routing_id = "legal-agent"
    result = call_agent(routing_id, agent_query)
    return {"status": "success", "recipe_used": recipe.get("name", recipe.get("filename", "unknown")), "report": result}


@app.post("/api/v1/export")
async def export_agent_endpoint(req: AgentExportRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")
    user_id = get_user_id_by_key(x_api_key)
    if not user_id:
        raise HTTPException(403, "Invalid Key")
    if not SDK_AVAILABLE:
        return {"status": "error", "message": "SDK not available on this server"}
    from agent_assembler.recipe import Recipe
    recipe_obj = Recipe(name=req.name, trigger_keywords=[req.name], skills=[], notes=req.description)
    if req.platform == "Coze":
        adapter = CozeAdapter(skills_dir=SKILL_BASE)
        config = adapter.export(recipe_obj)
    elif req.platform == "Qianwen":
        adapter = QianwenAdapter(skills_dir=SKILL_BASE)
        config = adapter.export(recipe_obj)
    else:
        return {"status": "error", "message": f"Unsupported platform: {req.platform}"}
    return {"status": "success", "platform": req.platform, "config": config}
