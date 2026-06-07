from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
import sys
import json
import time
import subprocess
import shlex
import re
import uuid
from pathlib import Path

# ── Universal Ingestor & Dispatcher Integration ──
INGESTOR_SCRIPT = os.path.expanduser("~/.hermes/recipes/scripts/universal_ingestor.py")
DISPATCHER_SCRIPT = os.path.expanduser("~/.openclaw/wiki/main/00-文档库/01-Projects/Agent-Assembler/code/dispatcher.py")
ROUTING_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "routing_schema.json")

# Ingestor helper functions (replicated from universal_ingestor.py for direct integration)
def _ingestor_extract_keywords(raw_data: str) -> dict:
    """
    Extract structured data (keywords, intent) from raw user input.
    Tries the Universal Ingestor first; falls back to inline heuristic extraction
    which is purpose-built for keyword/intent extraction (the ingestor's heuristic
    parser is domain-specific for tax/agriculture fields).
    """
    # Try the Universal Ingestor script first (if LLM is available, it works great)
    if os.path.exists(INGESTOR_SCRIPT) and os.path.exists(ROUTING_SCHEMA_PATH):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("universal_ingestor", INGESTOR_SCRIPT)
            if spec is not None:
                ui = importlib.util.module_from_spec(spec)
                if spec.loader is not None:
                    spec.loader.exec_module(ui)
                    result = ui.ingest(raw_data, ROUTING_SCHEMA_PATH)
                    # Only use result if keywords/intent were actually extracted
                    if result.get("keywords") and result.get("intent"):
                        return result
        except Exception:
            pass  # Fall through to inline heuristic extraction

    # Inline heuristic keyword extraction (purpose-built for routing)
    keywords = []
    for match in re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}', raw_data):
        keywords.append(match)
    keywords = list(dict.fromkeys(keywords))

    intent = _classify_intent(raw_data, keywords)

    return {
        "keywords": keywords[:10],
        "intent": intent,
        "topics": list(set(_extract_topics(raw_data)))
    }


def _classify_intent(text: str, keywords: list) -> str:
    """Classify user intent from keywords using heuristic rules."""
    text_lower = text.lower()
    keyword_set = set(k.lower() for k in keywords)

    intent_map = {
        "税务咨询": ["税", "税务", "纳税", "缴税", "增值税", "个税", "税收"],
        "农业评估": ["农业", "作物", "玉米", "产量", "受灾", "农田", "种植"],
        "利润计算": ["利润", "盈利", "赚", "营收", "收入", "成本", "毛利"],
        "薪资计算": ["工资", "薪资", "佣金", "提成", "绩效", "薪水"],
        "医疗报告": ["医疗", "体检", "报告", "病历", "诊断", "化验"],
        "二手车检测": ["二手车", "检测", "验车", "车况", "事故车"],
        "租金计算": ["租金", "租房", "押金", "房租", "租赁"],
        "育儿咨询": ["育儿", "教育", "儿童", "孩子", "宝宝", "婴儿"],
        "营销优化": ["营销", "广告", "推广", "ROI", "转化", "投放"],
        "反欺诈": ["欺诈", "风控", "异常", "风险", "审核"],
    }

    for intent, trigger_words in intent_map.items():
        for tw in trigger_words:
            if tw in text_lower or tw in keyword_set:
                return intent

    return "通用咨询"


def _extract_topics(text: str) -> list:
    """Extract domain topics from text."""
    topics = []
    topic_keywords = {
        "finance": ["财务", "资金", "账", "钱", "元", "万", "亿"],
        "agriculture": ["农业", "农", "作物", "田", "地", "产量", "亩"],
        "tax": ["税", "发票", "申报", "纳税"],
        "medical": ["医疗", "健康", "体检", "药", "医院"],
        "auto": ["车", "驾驶", "维修", "保险"],
        "real_estate": ["房", "租", "物业", "装修"],
        "education": ["教育", "学习", "培训", "考试"],
    }
    for topic, triggers in topic_keywords.items():
        if any(t in text for t in triggers):
            topics.append(topic)
    return topics


def _create_dispatcher():
    """Create and return an AgentDispatcher instance, or None if unavailable."""
    try:
        # Try importing from dispatcher.py directly
        if os.path.exists(DISPATCHER_SCRIPT):
            import importlib.util
            spec = importlib.util.spec_from_file_location("dispatcher", DISPATCHER_SCRIPT)
            disp_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(disp_mod)
            if hasattr(disp_mod, "AgentDispatcher"):
                return disp_mod.AgentDispatcher(MANIFESTS_DIR)
    except Exception as e:
        print(f"[WARN] Dispatcher init failed: {e}")
    return None


app = FastAPI(title="Agent Assembler Gateway", version="2.1.0")

DB_DIR = os.path.expanduser("~/.agent-assembler")
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "user_db.json")
USAGE_FILE = os.path.join(DB_DIR, "user_usage.json")

# ── Session Memory ──
SESSIONS = {}  # {session_id: [{"role": "...", "content": "..."}, ...]}

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

# Upload directory for multi-modal files
UPLOAD_DIR = os.path.expanduser("~/Desktop/agent-assembler/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Content Extractors (mock VLM/STT fallbacks) ──
def _extract_image_description(file_path: str, filename: str) -> str:
    """
    Extract a text description from an image.
    Tries VLM via OpenAI first; falls back to filename-based heuristics.
    """
    # Try VLM if API key is available
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            from openai import OpenAI
            api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
            model = os.environ.get("VISION_MODEL_NAME", "gpt-4o-mini")
            client = OpenAI(api_key=api_key, base_url=api_base)

            # Read and base64-encode the image
            import base64
            with open(file_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
            mime = mime_map.get(ext, "image/jpeg")

            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in detail. Extract any visible text, objects, people, and context."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
                    ]
                }],
                max_tokens=512,
            )
            desc = resp.choices[0].message.content.strip()
            if desc:
                print(f"[VLM] Image description: {desc[:100]}...")
                return desc
        except Exception as e:
            print(f"[WARN] VLM extraction failed: {e}, falling back to heuristic")

    # Fallback: derive description from filename and extension
    name_no_ext = os.path.splitext(filename)[0]
    # Clean up UUID-style or hash-style filenames
    clean_name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\s\-_]', ' ', name_no_ext).strip()
    if len(clean_name) < 3 or re.match(r'^[a-f0-9]{8,}$', clean_name.replace(' ', '')):
        clean_name = f"图片文件 {filename}"
    return f"[图片描述] {clean_name}（VLM不可用，使用文件名推断）"


def _extract_audio_transcription(file_path: str, filename: str) -> str:
    """
    Transcribe audio to text.
    Tries OpenAI Whisper first, then DashScope Paraformer, falls back to filename-based hint.
    """
    # ── Strategy 1: OpenAI Whisper ──
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from openai import OpenAI
            api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
            client = OpenAI(api_key=openai_key, base_url=api_base)

            with open(file_path, "rb") as f:
                resp = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                )
            text = resp.text.strip()
            if text:
                print(f"[STT] OpenAI Whisper transcription: {text[:100]}...")
                return text
        except Exception as e:
            print(f"[WARN] OpenAI STT failed: {e}")

    # ── Strategy 2: DashScope Paraformer (Alibaba Cloud) ──
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if dashscope_key:
        try:
            from openai import OpenAI
            dashscope_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            client = OpenAI(api_key=dashscope_key, base_url=dashscope_base)

            with open(file_path, "rb") as f:
                resp = client.audio.transcriptions.create(
                    model="paraformer-v2",
                    file=f,
                )
            text = resp.text.strip()
            if text:
                print(f"[STT] DashScope Paraformer transcription: {text[:100]}...")
                return text
        except Exception as e:
            print(f"[WARN] DashScope Paraformer STT failed: {e}")

    # ── Fallback: no STT API available ──
    if not openai_key and not dashscope_key:
        print("[WARN] No STT API key configured. Set OPENAI_API_KEY or DASHSCOPE_API_KEY for voice transcription.")

    name_no_ext = os.path.splitext(filename)[0]
    clean_name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\s\-_]', ' ', name_no_ext).strip()
    if len(clean_name) < 3 or re.match(r'^[a-f0-9]{8,}$', clean_name.replace(' ', '')):
        clean_name = "语音消息"
    return f"[语音转写] {clean_name}（STT不可用，使用文件名推断）"


def _extract_text_content(file_path: str) -> str:
    """Read text content from a text file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"[WARN] Text extraction failed: {e}")
        return ""

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

MANIFESTS_DIR = os.path.expanduser("~/.openclaw/wiki/main/00-文档库/01-Projects/Agent-Assembler/code/manifests")

# Initialize the Agent Dispatcher at startup
dispatcher = _create_dispatcher()

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

# --- 多模态上传 ---
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic'}
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.webm', '.amr'}

@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...), file_type: str = Form(None)):
    """Handle multi-modal file uploads (image/audio) from the Mini Program.
    
    Full chain: File → Content Extractor (VLM/STT) → Universal Ingestor → Dispatcher → Routing.
    """
    # Determine file type from extension or form field
    ext = os.path.splitext(file.filename or "")[1].lower()
    original_filename = file.filename or "unknown"
    
    if file_type == "audio" or ext in ALLOWED_AUDIO_EXTENSIONS:
        media_type = "audio"
        allowed = ALLOWED_AUDIO_EXTENSIONS
    elif file_type == "image" or ext in ALLOWED_IMAGE_EXTENSIONS:
        media_type = "image"
        allowed = ALLOWED_IMAGE_EXTENSIONS
    else:
        # Default to image if extension looks like one
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            media_type = "image"
            allowed = ALLOWED_IMAGE_EXTENSIONS
        elif ext in ALLOWED_AUDIO_EXTENSIONS:
            media_type = "audio"
            allowed = ALLOWED_AUDIO_EXTENSIONS
        elif ext in ('.txt', '.md', '.csv', '.json', '.log'):
            media_type = "text"
            allowed = {'.txt', '.md', '.csv', '.json', '.log'}
        else:
            return {"status": "error", "message": f"不支持的文件类型: {ext}"}
    
    if ext not in allowed:
        return {"status": "error", "message": f"不支持的{media_type}格式: {ext}"}
    
    # Generate unique filename to avoid collisions
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    
    # Save file
    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
    except Exception as e:
        return {"status": "error", "message": f"保存文件失败: {str(e)}"}
    
    # Build a local URL / file path for reference
    file_url = f"/uploads/{unique_name}"
    
    # ── Step 1: Extract text content from the uploaded file ──
    if media_type == "image":
        extracted_text = _extract_image_description(save_path, original_filename)
    elif media_type == "audio":
        extracted_text = _extract_audio_transcription(save_path, original_filename)
    elif media_type == "text":
        extracted_text = _extract_text_content(save_path)
    else:
        extracted_text = f"[{media_type}] 文件已保存: {original_filename}"
    
    # ── Step 2: Universal Ingestor — extract keywords/intent from the text ──
    extracted_data = _ingestor_extract_keywords(extracted_text)
    keywords = extracted_data.get("keywords", [])
    intent = extracted_data.get("intent", "未知")
    topics = extracted_data.get("topics", [])
    
    # ── Step 3: Dispatcher — route to the best-matching Agent ──
    routing_result = {"status": "unmatched", "message": "未找到匹配的 Agent"}
    routed_to = None
    agent_info = None

    if dispatcher is not None:
        try:
            routing_result = dispatcher.route(keywords)
        except Exception as e:
            routing_result = {"status": "error", "message": f"Dispatcher 路由失败: {str(e)}"}

    if routing_result.get("status") == "routed":
        agent = routing_result.get("agent", {})
        routed_to = agent.get("name", "Unknown")
        agent_info = {
            "name": routed_to,
            "id": agent.get("id", "unknown"),
            "description": agent.get("description", ""),
            "tags": agent.get("tags", [])
        }
        score = routing_result.get("score", 0)
        print(f"[Upload→Dispatcher] Routing {original_filename} to: {routed_to} (score: {score})")
    elif routing_result.get("status") == "conflict":
        candidates = routing_result.get("candidates", [])
        routed_to = "conflict"
        agent_info = {"candidates": [c.get("name", "Unknown") for c in candidates]}
        print(f"[Upload→Dispatcher] Conflict for {original_filename}: {agent_info['candidates']}")
    else:
        routed_to = "unmatched"
        print(f"[Upload→Dispatcher] No agent matched for {original_filename}")
    
    # ── Step 4: Build enriched response ──
    return {
        "status": "success",
        "file_url": file_url,
        "file_path": save_path,
        "type": media_type,
        "filename": original_filename,
        "extracted_text": extracted_text,
        "routed_to": routed_to,
        "agent": agent_info,
        "extracted_data": {
            "keywords": keywords,
            "intent": intent,
            "topics": topics
        }
    }

# --- Agent Shelf: 动态列出所有可用 Agent ---
@app.get("/api/v1/agents")
async def list_agents():
    """Scan manifests directory and return a list of available agents."""
    agents = []
    if not os.path.exists(MANIFESTS_DIR):
        return {"agents": []}
    
    for f in os.listdir(MANIFESTS_DIR):
        if not f.endswith(".json"):
            continue
        filepath = os.path.join(MANIFESTS_DIR, f)
        try:
            data = json.load(open(filepath, encoding="utf-8"))
            agents.append({
                "id": data.get("id", f.replace(".json", "")),
                "name": data.get("name", "Unknown Agent"),
                "description": data.get("description", ""),
                "tags": data.get("tags", [])
            })
        except Exception:
            continue
    
    # Sort by name for consistent display
    agents.sort(key=lambda a: a["name"])
    return {"agents": agents}

# --- Smart Chat: Universal Ingestor → Dispatcher → Routing ---
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    file_path: Optional[str] = None

@app.post("/api/v1/chat")
async def chat(req: ChatRequest):
    """
    Full chain: User Input → Universal Ingestor → Dispatcher → Agent Routing.
    
    1. Extract structured data (keywords, intent) from the user message.
    2. Pass keywords to the Dispatcher to find the best-matching Agent.
    3. Return routing result with the matched Agent name.
    """
    user_input = req.message.strip()
    if not user_input:
        return {"status": "error", "message": "消息不能为空"}

    # Step 1: Universal Ingestor — extract structured data
    extracted = _ingestor_extract_keywords(user_input)
    keywords = extracted.get("keywords", [])
    intent = extracted.get("intent", "未知")
    topics = extracted.get("topics", [])

    # Step 2: Dispatcher — route to the best-matching Agent
    routing_result = {"status": "unmatched", "message": "未找到匹配的 Agent"}
    agent_name = None

    if dispatcher is not None:
        try:
            routing_result = dispatcher.route(keywords)
        except Exception as e:
            routing_result = {"status": "error", "message": f"Dispatcher 路由失败: {str(e)}"}

    # Step 3: Build response
    if routing_result.get("status") == "routed":
        agent = routing_result.get("agent", {})
        agent_name = agent.get("name", "Unknown")
        agent_id = agent.get("id", "unknown")
        score = routing_result.get("score", 0)
        system_prompt = agent.get("system_prompt", agent.get("description", ""))

        # Log routing decision
        print(f"[Dispatcher] Routing to: {agent_name} (score: {score})")
        if system_prompt:
            print(f"[Dispatcher] Injected system prompt for {agent_name}")

        # ── Session Memory: if session_id provided, do full LLM chat ──
        if req.session_id:
            # Retrieve or create session history
            history = SESSIONS.get(req.session_id, [])

            # Load system prompt from manifest (use explicit agent_id if provided)
            manifest_prompt = _load_agent_system_prompt(req.agent_id or agent_id)
            if not manifest_prompt:
                manifest_prompt = system_prompt  # fallback from routing

            # Build messages: system + history + current user message
            messages = []
            if manifest_prompt:
                messages.append({"role": "system", "content": manifest_prompt})
            messages.extend(history)
            messages.append({"role": "user", "content": user_input})

            # Call LLM with full context
            llm_response = _call_llm(messages)

            # Update session history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": llm_response})

            # Trim history if > 20 messages (keep last 20)
            if len(history) > 20:
                history = history[-20:]

            SESSIONS[req.session_id] = history

            return {
                "status": "success",
                "session_id": req.session_id,
                "message": llm_response,
                "agent": {
                    "name": agent_name,
                    "id": agent_id,
                    "description": agent.get("description", ""),
                    "tags": agent.get("tags", [])
                },
                "history_length": len(history),
                "routing_score": score,
                "extracted": {
                    "keywords": keywords,
                    "intent": intent,
                    "topics": topics
                }
            }

        return {
            "status": "success",
            "message": f"已为您路由到 {agent_name}",
            "agent": {
                "name": agent_name,
                "id": agent_id,
                "description": agent.get("description", ""),
                "tags": agent.get("tags", [])
            },
            "system_prompt": system_prompt,
            "routing_score": score,
            "extracted": {
                "keywords": keywords,
                "intent": intent,
                "topics": topics
            }
        }
    elif routing_result.get("status") == "conflict":
        candidates = routing_result.get("candidates", [])
        candidate_names = [c.get("name", "Unknown") for c in candidates]
        return {
            "status": "conflict",
            "message": f"多个 Agent 匹配: {', '.join(candidate_names)}",
            "candidates": candidate_names,
            "extracted": {
                "keywords": keywords,
                "intent": intent,
                "topics": topics
            }
        }
    else:
        # Fallback: return the extracted info even if no agent matched
        return {
            "status": "unmatched",
            "message": "暂未找到匹配的 Agent，已为您记录需求",
            "extracted": {
                "keywords": keywords,
                "intent": intent,
                "topics": topics
            }
        }

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
    # 4a. Check if recipe has a script to execute
    script_path = recipe.get("script_path") or recipe.get("script") or recipe.get("code")
    
    if script_path:
        # Execute the script first, then use LLM to format results
        script_args = _extract_script_args(recipe, req.query)
        success, script_output = _run_script(script_path, script_args)
        
        if success:
            # Script succeeded: ask LLM to format/explain the result
            skill_content = load_skill(recipe)
            agent_query = (
                f"You are an assistant. A calculation/processing tool has produced the following result.\n"
                f"Strictly follow this skill logic for context:\n{skill_content}\n\n"
                f"TOOL OUTPUT:\n{script_output}\n\n"
                f"User Query: {req.query}\n\n"
                f"Explain this result to the user in a clear, professional manner. "
                f"Do NOT recalculate — the tool output above is the definitive result."
            )
        else:
            # Script failed: fall back to LLM-only with error note
            print(f"[Script Engine] Script execution failed, falling back to LLM: {script_output}")
            skill_content = load_skill(recipe)
            agent_query = (
                f"Strictly follow this skill logic:\n{skill_content}\n\n"
                f"User Query: {req.query}\n\n"
                f"Note: A calculation script was attempted but failed: {script_output}. "
                f"Please answer the user's query using your knowledge instead."
            )
    else:
        # No script: proceed with original LLM-only logic
        skill_content = load_skill(recipe)
        agent_query = f"Strictly follow this skill logic:\n{skill_content}\n\nUser Query: {req.query}"
    
    routing_id = recipe.get("routing")
    if not routing_id:
        routing_id = "legal-agent"  # Fallback to default if routing is null/missing
    result = call_agent(routing_id, agent_query)
    
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

# --- AutoCraft reference paths ---
AUTOCRAFT_REF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autocraft", "references")
RECIPE_SCHEMA_PATH = os.path.join(AUTOCRAFT_REF_DIR, "recipe_schema.json")
RECIPE_TEMPLATE_PATH = os.path.join(AUTOCRAFT_REF_DIR, "recipe_template.py")

# Cache schema content for prompt injection
def _load_recipe_schema_text():
    """Load recipe schema JSON text for embedding in LLM prompts."""
    try:
        with open(RECIPE_SCHEMA_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _validate_recipe_json(data: dict) -> list[str]:
    """
    Manual validation of a recipe dict against the core schema rules.
    Returns a list of error strings (empty = valid).
    Replaces jsonschema to avoid external dependency.
    """
    errors: list[str] = []

    # Required: name (non-empty string)
    if "name" not in data:
        errors.append("Missing required field: 'name'")
    elif not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("'name' must be a non-empty string")

    # Required: trigger_keywords (non-empty list of strings)
    if "trigger_keywords" not in data:
        errors.append("Missing required field: 'trigger_keywords'")
    elif not isinstance(data["trigger_keywords"], list):
        errors.append("'trigger_keywords' must be a list")
    elif len(data["trigger_keywords"]) == 0:
        errors.append("'trigger_keywords' must not be empty")
    elif not all(isinstance(kw, str) for kw in data["trigger_keywords"]):
        errors.append("All items in 'trigger_keywords' must be strings")

    # Optional: skills (list of strings)
    if "skills" in data and not isinstance(data["skills"], list):
        errors.append("'skills' must be a list of strings")

    # Optional: notes (string)
    if "notes" in data and not isinstance(data["notes"], str):
        errors.append("'notes' must be a string")

    # Optional: routing (object/dict)
    if "routing" in data and not isinstance(data["routing"], dict):
        errors.append("'routing' must be an object")

    # Optional: engine_config (object/dict)
    if "engine_config" in data and not isinstance(data["engine_config"], dict):
        errors.append("'engine_config' must be an object")

    return errors


# --- 动态炼金 ---
def _extract_json_from_response(text: str):
    """Extract the first valid JSON object from LLM response text.

    Tries fenced code block first (```json ... ```), then falls back to
    finding the outermost matching braces by counting.
    """
    # 1) Try fenced code block
    import re
    m = re.search(r'```json\s*\n(.*?)```', text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass  # fall through

    # 2) Try any fenced block (language-agnostic)
    m = re.search(r'```\s*\n(.*?)```', text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 3) Find first '{' and last '}' and attempt parse
    first = text.find('{')
    last = text.rfind('}')
    if first != -1 and last != -1 and last > first:
        candidate = text[first:last + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


async def auto_craft_and_run(query, user_id, max_retries: int = 3):
    """
    Auto-generate a recipe + skill when no existing recipe matches the query.

    Includes schema-guided prompt, JSON extraction from LLM response,
    schema validation with retry logic (up to max_retries attempts).
    """
    sanitized_name = sanitize(query)
    recipe_path = os.path.join(AUTO_DIR, f"{sanitized_name}.json")
    skill_path = os.path.join(SKILL_AUTO_DIR, f"{sanitized_name}.md")

    # Load schema for prompt injection (helps LLM generate valid JSON)
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

        # Ensure directories exist before writing
        os.makedirs(AUTO_DIR, exist_ok=True)
        os.makedirs(SKILL_AUTO_DIR, exist_ok=True)

        # Call DashScope directly to generate recipe JSON + answer
        result = _dashscope_chat([{"role": "user", "content": prompt}])

        # ── Extract JSON from the LLM response text ──
        recipe_data = _extract_json_from_response(result)
        if recipe_data is None:
            last_error = "Could not extract valid JSON from LLM response"
            print(f"[AutoCraft] {last_error} — retrying...")
            continue

        # ── Manual schema validation ──
        validation_errors = _validate_recipe_json(recipe_data)
        if validation_errors:
            last_error = f"Schema validation failed: {'; '.join(validation_errors)}"
            print(f"[AutoCraft] {last_error} — retrying...")
            continue

        # ── Write the validated recipe JSON to disk ──
        with open(recipe_path, "w", encoding="utf-8") as f:
            json.dump(recipe_data, f, indent=2, ensure_ascii=False)
        print(f"[AutoCraft] Wrote recipe to {recipe_path}")

        # ── All checks passed ──
        print(f"[AutoCraft] Recipe '{recipe_data.get('name')}' validated successfully on attempt {attempt}")
        return {
            "status": "auto_generated",
            "message": "已现场生成配方并执行",
            "report": result,
            "recipe": recipe_data.get("name", sanitized_name),
            "attempts": attempt,
        }

    # All retries exhausted
    print(f"[AutoCraft] FAILED after {max_retries} attempts. Last error: {last_error}")
    return {
        "status": "auto_craft_failed",
        "message": f"配方生成失败（{max_retries} 次重试后仍未通过验证）",
        "report": result or "无结果",
        "last_error": last_error,
        "attempts": max_retries,
    }

def sanitize(q): return re.sub(r'[^\w\u4e00-\u9fa5]', '_', q)[:20]

# --- Script Execution Engine ---
SCRIPT_DIRS = [
    os.path.expanduser("~/.hermes/recipes/scripts"),
    "/data/jit/recipes/scripts",
]

def _validate_script_path(script_path: str) -> tuple[bool, str]:
    """
    Validate that a script path is safe to execute.
    Returns (is_safe, resolved_path_or_error_message).
    """
    if not script_path:
        return False, "Empty script path"

    # Reject path traversal
    if ".." in script_path:
        return False, f"Path traversal not allowed: {script_path}"

    # Reject dangerous paths
    dangerous = ["/bin/", "/sbin/", "/usr/bin/", "/usr/sbin/", "/etc/", "/dev/", "/proc/", "/sys/"]
    for dp in dangerous:
        if script_path.startswith(dp):
            return False, f"Dangerous path rejected: {script_path}"

    # If already absolute and points to a .py file that exists, allow it
    if os.path.isabs(script_path):
        if not script_path.endswith(".py"):
            return False, f"Script must be a .py file: {script_path}"
        if os.path.exists(script_path):
            return True, script_path
        return False, f"Script file not found: {script_path}"

    # Relative path: resolve against known script directories
    for base in SCRIPT_DIRS:
        candidate = os.path.normpath(os.path.join(base, script_path))
        if not candidate.startswith(base):
            continue  # path traversal escape
        if os.path.exists(candidate):
            return True, candidate

    # Last resort: check if it exists as-is relative to CWD
    candidate = os.path.normpath(os.path.abspath(script_path))
    if os.path.exists(candidate) and candidate.endswith(".py"):
        return True, candidate

    return False, f"Script file not found in any known directory: {script_path}"


def _run_script(script_path: str, args: dict) -> tuple[bool, str]:
    """
    Execute a Python script with the given arguments.
    Returns (success: bool, output: str).
    """
    is_safe, resolved = _validate_script_path(script_path)
    if not is_safe:
        return False, f"[Script Error] {resolved}"

    print(f"[Script Engine] Executing: {resolved} with args: {json.dumps(args, ensure_ascii=False)[:200]}")

    try:
        result = subprocess.run(
            ["python3", resolved, json.dumps(args, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            print(f"[Script Engine] Success: {output[:200]}...")
            return True, output
        else:
            err = result.stderr.strip()[:500]
            print(f"[Script Engine] Error (rc={result.returncode}): {err}")
            return False, f"[Script Error] {err}"
    except subprocess.TimeoutExpired:
        return False, "[Script Error] Execution timed out (60s)"
    except FileNotFoundError:
        return False, "[Script Error] python3 not found on this system"
    except Exception as e:
        return False, f"[Script Error] {str(e)}"


def _extract_script_args(recipe: dict, query: str) -> dict:
    """
    Extract script arguments from the recipe definition and user query.
    Looks for 'script_args' in the recipe, and tries to parse key=value
    patterns from the query as supplementary arguments.
    """
    # Start with defaults from recipe
    args = recipe.get("script_args", {}).copy() if isinstance(recipe.get("script_args"), dict) else {}

    # Also check engine_config for args
    ec = recipe.get("engine_config", {})
    if isinstance(ec, dict) and "script_args" in ec:
        args.update(ec["script_args"])

    # Parse key=value patterns from query
    for match in re.findall(r'(\w+)\s*[=:]\s*([^\s,;]+)', query):
        key, val = match
        args[key] = val

    # Always include the raw query
    args["query"] = query

    return args


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


def find_skill_in_directory(base_dir, filename):
    """Recursively search for SKILL.md or filename.md in base_dir."""
    if not os.path.exists(base_dir): return None
    for root, dirs, files in os.walk(base_dir):
        # Skip AutoCreated skills if we are searching main skills (optional, but good for performance)
        if "AutoCreated" in root and base_dir in root:
            continue
            
        # Strategy A: Look for SKILL.md in a folder named like the skill
        if os.path.basename(root) == filename:
            skill_file = os.path.join(root, "SKILL.md")
            if os.path.exists(skill_file):
                return skill_file
        
        # Strategy B: Look for {filename}.md directly
        if f"{filename}.md" in files:
            return os.path.join(root, f"{filename}.md")
            
    return None

def load_skill(recipe):
    fn = recipe.get("filename", "unknown")
    skill_rel = recipe.get("skill", "")
    paths = []
    
    # 1. Try specific relative path (Cloud preference)
    if IS_CLOUD and skill_rel:
        path = os.path.join(SKILL_BASE, f"{skill_rel}/SKILL.md")
        if os.path.exists(path): return open(path, encoding="utf-8").read()
    
    # 2. Try filename in AutoCreated
    auto_path = f"{SKILL_AUTO_DIR}/{fn}.md"
    if os.path.exists(auto_path): return open(auto_path, encoding="utf-8").read()

    # 3. Generic Recursive Search (Replaces hardcoded categories)
    found = find_skill_in_directory(SKILL_BASE, fn)
    if found:
        return open(found, encoding="utf-8").read()

    # Fallback
    return "Provide expert advice based on general knowledge."


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


def _load_agent_system_prompt(agent_id: str) -> str:
    """Load an agent's system_prompt from its manifest file."""
    if not agent_id or not os.path.exists(MANIFESTS_DIR):
        return ""
    for f in os.listdir(MANIFESTS_DIR):
        if not f.endswith(".json"):
            continue
        filepath = os.path.join(MANIFESTS_DIR, f)
        try:
            data = json.load(open(filepath, encoding="utf-8"))
            # Match by id field or by filename stem
            if data.get("id") == agent_id or f.replace(".json", "") == agent_id:
                return data.get("system_prompt", data.get("description", ""))
        except Exception:
            continue
    return ""


def _call_llm(messages: list) -> str:
    """Call an OpenAI/DashScope-compatible LLM with a full messages list."""
    api_key = os.environ.get("OPENAI_API_KEY", "") or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        return "LLM API key not configured (set OPENAI_API_KEY or DASHSCOPE_API_KEY)."

    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model = os.environ.get("CHAT_MODEL_NAME", os.environ.get("MODEL_NAME", "qwen-plus"))

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=api_base)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"LLM call failed: {str(e)}"


def _dashscope_chat(messages: list, system_prompt: Optional[str] = None) -> str:
    """
    Direct DashScope chat completion via the OpenAI-compatible API.
    No external orchestration dependency — just a raw LLM call.
    """
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
            model=model,
            messages=built_messages,
            max_tokens=8192,
            temperature=0.7,
        )
        content = resp.choices[0].message.content
        if content:
            print(f"[DashScope] qwen3.6-plus response: {content[:100]}...")
            return content.strip()
        return "[Error] Empty response from DashScope"
    except Exception as e:
        print(f"[WARN] DashScope chat failed: {e}")
        return f"[Error] DashScope API error: {str(e)}"


def call_agent(agent_id, msg):
    try:
        safe_msg = shlex.quote(msg)
        cmd_str = f"openclaw agent --agent {agent_id} --message {safe_msg} --json --timeout 120"
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=130)
        
        # Robustness: Extract JSON block from stdout (OpenClaw sometimes prints logs before JSON)
        stdout = res.stdout
        if '{' in stdout:
            json_str = stdout[stdout.find('{'):]
            try:
                data = json.loads(json_str)
                payloads = data.get("result", {}).get("payloads", [])
                if payloads and "text" in payloads[0]:
                    return payloads[0]["text"]
            except json.JSONDecodeError:
                pass
                
        # If still no result, return error details
        err_msg = res.stderr.strip()[:200] if res.stderr else "Unknown error"
        return f"执行失败: {err_msg}"
    except Exception as e: 
        return f"超时或错误: {str(e)}"

