from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os
import json
import time
import subprocess
import shlex
import re

app = FastAPI(title="Agent Assembler Gateway", version="2.1.0")

DB_FILE = "/tmp/user_db.json"
USAGE_FILE = "/tmp/user_usage.json"

# 自适应路径：本地 Mac vs 云端 Linux
IS_CLOUD = os.path.exists("/data/jit")
if IS_CLOUD:
    RECIPE_BASE = "/data/jit/recipes"
    SKILL_BASE = "/data/jit/skills"
    AUTO_DIR = "/data/jit/recipes/AutoCreated"
    SKILL_AUTO_DIR = os.path.join(AUTO_DIR, "Skills")
else:
    RECIPE_BASE = os.path.expanduser("~/Desktop/配方")
    SKILL_BASE = os.path.expanduser("~/.hermes/skills")
    AUTO_DIR = os.path.expanduser("~/Desktop/配方/AutoCreated")
    SKILL_AUTO_DIR = os.path.join(AUTO_DIR, "Skills")
os.makedirs(AUTO_DIR, exist_ok=True)
os.makedirs(SKILL_AUTO_DIR, exist_ok=True)

# SDK import (graceful fallback if not installed)
try:
    from agent_assembler import Assembler
    from agent_assembler.adapters import CozeAdapter, QianwenAdapter
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# 初始化 DB
if not os.path.exists(DB_FILE): open(DB_FILE, "w").write("{}")
if not os.path.exists(USAGE_FILE): open(USAGE_FILE, "w").write("{}")

def load_json(f):
    try: return json.load(open(f))
    except: return {}
def save_json(f, data):
    json.dump(data, open(f, "w"), indent=2)

class QueryRequest(BaseModel):
    query: str

class AgentExportRequest(BaseModel):
    name: str
    description: str
    platform: str  # "Coze" or "Qianwen"

class LoginResponse(BaseModel):
    status: str
    api_key: str
    user_id: str

# --- 登录 ---
@app.get("/api/v1/login", response_model=LoginResponse)
async def login(device_id: str = "test_device"):
    db = load_json(DB_FILE)
    if device_id not in db or isinstance(db[device_id], str):
        db[device_id] = {"api_key": f"key_{device_id}_{int(time.time())}", "plan": "free"}
        save_json(DB_FILE, db)
    
    return {"status": "success", "api_key": db[device_id]["api_key"], "user_id": device_id}

# --- 核心路由 ---
@app.post("/api/v1/run")
async def run_recipe(req: QueryRequest, x_api_key: str = Header(None)):
    if not x_api_key: raise HTTPException(401, "Missing API Key")
    
    user_id = get_user_id_by_key(x_api_key)
    if not user_id: raise HTTPException(403, "Invalid Key")
    
    db = load_json(DB_FILE)
    user_info = db.get(user_id, {})
    user_plan = user_info.get("plan", "free") if isinstance(user_info, dict) else "free"
    
    # 1. 匹配配方
    recipe = find_recipe(req.query)
    
    if not recipe:
        return await auto_craft_and_run(req.query, user_id)
        
    # 2. 付费拦截
    if is_premium(recipe) and user_plan == "free":
        return paywall_response("Premium 配方需要升级解锁。")
        
    # 3. 每日次数拦截
    if user_plan == "free":
        if check_usage(user_id) >= 3:
            return paywall_response("今日免费额度已用完。")
    increment_usage(user_id)

    # 4. 执行
    skill_content = load_skill(recipe)
    agent_query = f"Strictly follow this skill logic:\n{skill_content}\n\nUser Query: {req.query}"
    result = call_agent(recipe.get("routing", "legal-agent"), agent_query)
    
    return {"status": "success", "recipe_used": recipe.get("name", recipe.get("filename", "unknown")), "report": result}

# --- 新增: SDK Adapter 导出 API ---
@app.post("/api/v1/export")
async def export_agent(req: AgentExportRequest, x_api_key: str = Header(None)):
    """Export an Agent config to target platform DSL using SDK Adapters."""
    if not x_api_key: raise HTTPException(401, "Missing API Key")
    
    user_id = get_user_id_by_key(x_api_key)
    if not user_id: raise HTTPException(403, "Invalid Key")
    
    if not SDK_AVAILABLE:
        return {"status": "error", "message": "SDK not available on this server"}
    
    from agent_assembler.recipe import Recipe
    
    recipe = Recipe(
        name=req.name,
        trigger_keywords=[req.name],
        skills=[],
        notes=req.description
    )
    
    if req.platform == "Coze":
        adapter = CozeAdapter(skills_dir=SKILL_BASE)
        config = adapter.export(recipe)
    elif req.platform == "Qianwen":
        adapter = QianwenAdapter(skills_dir=SKILL_BASE)
        config = adapter.export(recipe)
    else:
        return {"status": "error", "message": f"Unsupported platform: {req.platform}"}
    
    return {"status": "success", "platform": req.platform, "config": config}

# --- 动态炼金 ---
async def auto_craft_and_run(query, user_id):
    prompt = f"""User asked: "{query}". No recipe matched.
You are a Recipe Architect. Do these 3 steps using your tools:
1. CREATE a Recipe JSON at: {AUTO_DIR}/{sanitize(query)}.json (Follow standard trigger/skills/routing format)
2. CREATE a Skill MD at: {SKILL_AUTO_DIR}/{sanitize(query)}.md (Step-by-step execution logic)
3. EXECUTE the logic and give a PROFESSIONAL ANSWER to the user.
Output ONLY the final answer. Do not explain the generation process."""
    
    result = call_agent("engineering-stage-agent", prompt)
    
    return {"status": "auto_generated", "message": "已现场生成配方并执行", "report": result}

def sanitize(q): return re.sub(r'[^\w\u4e00-\u9fa5]', '_', q)[:20]

# --- 辅助函数 ---
def is_premium(r): return r.get("_source_premium", False)
def paywall_response(msg): return {"status": "paywall", "message": msg, "price": "9.9", "title": "升级 Pro 解锁无限配方"}

def get_user_id_by_key(key):
    db = load_json(DB_FILE)
    for uid, info in db.items():
        if isinstance(info, str) and info == key: return uid
        if isinstance(info, dict) and info.get("api_key") == key: return uid
    return None

def find_recipe(query):
    base = RECIPE_BASE
    if not os.path.exists(base): return None
    
    # 第一轮：普通配方优先匹配
    for root, _, files in os.walk(base):
        if "Premium_Assets" in root: continue
        for f in files:
            if f.endswith(".json"):
                try:
                    d = json.load(open(os.path.join(root, f)))
                    for kw in d.get("trigger_keywords", []):
                        if kw in query:
                            d["_source_premium"] = False
                            d["filename"] = f.replace(".json", "")
                            return d
                except: pass
    
    # 第二轮：Premium 兜底
    for root, _, files in os.walk(base):
        if "Premium_Assets" not in root: continue
        for f in files:
            if f.endswith(".json"):
                try:
                    d = json.load(open(os.path.join(root, f)))
                    for kw in d.get("trigger_keywords", []):
                        if kw in query:
                            d["_source_premium"] = True
                            d["filename"] = f.replace(".json", "")
                            return d
                except: pass
    
    return None

def load_skill(recipe):
    fn = recipe.get("filename", "unknown")
    skill_rel = recipe.get("skill", "")
    paths = []
    
    if IS_CLOUD and skill_rel:
        paths.append(os.path.join(SKILL_BASE, f"{skill_rel}/SKILL.md"))
    
    for cat in ["Legal", "CulturalTourism", "finance", "devops", "domain", "operations"]:
        paths.append(os.path.join(SKILL_BASE, f"{cat}/{fn}/SKILL.md"))
    
    paths.append(f"{SKILL_AUTO_DIR}/{fn}.md")
    for p in paths:
        if os.path.exists(p):
            return open(p, encoding="utf-8").read()
    return "Provide expert advice based on general knowledge."

def call_agent(agent_id, msg):
    try:
        safe_msg = shlex.quote(msg)
        cmd_str = f"openclaw agent --agent {agent_id} --message {safe_msg} --json --timeout 120"
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=130)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            payloads = data.get("result", {}).get("payloads", [])
            if payloads and "text" in payloads[0]: return payloads[0]["text"]
        return f"执行失败: {res.stderr[:100]}"
    except Exception as e: return f"超时或错误: {str(e)}"

def check_usage(uid):
    usage = load_json(USAGE_FILE)
    today = time.strftime("%Y-%m-%d")
    return usage.get(uid, {}).get(today, 0)

def increment_usage(uid):
    usage = load_json(USAGE_FILE)
    today = time.strftime("%Y-%m-%d")
    usage.setdefault(uid, {})
    usage[uid][today] = usage[uid].get(today, 0) + 1
    save_json(USAGE_FILE, usage)
