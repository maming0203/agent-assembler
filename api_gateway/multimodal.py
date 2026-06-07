"""Multi-modal module — file upload, VLM extraction, STT transcription, Ingestor keywords."""
import base64
import importlib.util
import os
import re
import uuid


# ── Path helpers (lazy to avoid circular import with core) ──
def _get_paths():
    """Return shared paths from core module."""
    from .core import DISPATCHER_SCRIPT, INGESTOR_SCRIPT, MANIFESTS_DIR, ROUTING_SCHEMA_PATH, UPLOAD_DIR
    return DISPATCHER_SCRIPT, INGESTOR_SCRIPT, MANIFESTS_DIR, ROUTING_SCHEMA_PATH, UPLOAD_DIR


# ── Ingestor helpers ──
def _ingestor_extract_keywords(raw_data: str) -> dict:
    """Extract structured data (keywords, intent) from raw user input."""
    _, INGESTOR_SCRIPT, _, ROUTING_SCHEMA_PATH, _ = _get_paths()
    if os.path.exists(INGESTOR_SCRIPT) and os.path.exists(ROUTING_SCHEMA_PATH):
        try:
            spec = importlib.util.spec_from_file_location("universal_ingestor", INGESTOR_SCRIPT)
            if spec is not None:
                ui = importlib.util.module_from_spec(spec)
                if spec.loader is not None:
                    spec.loader.exec_module(ui)
                    result = ui.ingest(raw_data, ROUTING_SCHEMA_PATH)
                    if result.get("keywords") and result.get("intent"):
                        return result
        except Exception:
            pass
    keywords = []
    for match in re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}", raw_data):
        keywords.append(match)
    keywords = list(dict.fromkeys(keywords))
    intent = _classify_intent(raw_data, keywords)
    return {
        "keywords": keywords[:10],
        "intent": intent,
        "topics": list(set(_extract_topics(raw_data))),
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
    DISPATCHER_SCRIPT, _, MANIFESTS_DIR, _, _ = _get_paths()
    try:
        if os.path.exists(DISPATCHER_SCRIPT):
            spec = importlib.util.spec_from_file_location("dispatcher", DISPATCHER_SCRIPT)
            disp_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(disp_mod)
            if hasattr(disp_mod, "AgentDispatcher"):
                return disp_mod.AgentDispatcher(MANIFESTS_DIR)
    except Exception as e:
        print(f"[WARN] Dispatcher init failed: {e}")
    return None


# ── Content Extractors ──
def _extract_image_description(file_path: str, filename: str) -> str:
    """Extract text description from image via VLM or fallback."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            from openai import OpenAI
            api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
            model = os.environ.get("VISION_MODEL_NAME", "gpt-4o-mini")
            client = OpenAI(api_key=api_key, base_url=api_base)
            with open(file_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
            mime = mime_map.get(ext, "image/jpeg")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": "Describe this image in detail. Extract any visible text, objects, people, and context."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
                ]}],
                max_tokens=512,
            )
            desc = resp.choices[0].message.content.strip()
            if desc:
                print(f"[VLM] Image description: {desc[:100]}...")
                return desc
        except Exception as e:
            print(f"[WARN] VLM extraction failed: {e}, falling back to heuristic")
    name_no_ext = os.path.splitext(filename)[0]
    clean_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5\s\-_]", " ", name_no_ext).strip()
    if len(clean_name) < 3 or re.match(r"^[a-f0-9]{8,}$", clean_name.replace(" ", "")):
        clean_name = f"图片文件 {filename}"
    return f"[图片描述] {clean_name}（VLM不可用，使用文件名推断）"


def _extract_audio_transcription(file_path: str, filename: str) -> str:
    """Transcribe audio via OpenAI Whisper or DashScope Paraformer."""
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from openai import OpenAI
            api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
            client = OpenAI(api_key=openai_key, base_url=api_base)
            with open(file_path, "rb") as f:
                resp = client.audio.transcriptions.create(model="whisper-1", file=f)
            text = resp.text.strip()
            if text:
                print(f"[STT] OpenAI Whisper transcription: {text[:100]}...")
                return text
        except Exception as e:
            print(f"[WARN] OpenAI STT failed: {e}")
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if dashscope_key:
        try:
            from openai import OpenAI
            dashscope_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            client = OpenAI(api_key=dashscope_key, base_url=dashscope_base)
            with open(file_path, "rb") as f:
                resp = client.audio.transcriptions.create(model="paraformer-v2", file=f)
            text = resp.text.strip()
            if text:
                print(f"[STT] DashScope Paraformer transcription: {text[:100]}...")
                return text
        except Exception as e:
            print(f"[WARN] DashScope Paraformer STT failed: {e}")
    if not openai_key and not dashscope_key:
        print("[WARN] No STT API key configured. Set OPENAI_API_KEY or DASHSCOPE_API_KEY.")
    name_no_ext = os.path.splitext(filename)[0]
    clean_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5\s\-_]", " ", name_no_ext).strip()
    if len(clean_name) < 3 or re.match(r"^[a-f0-9]{8,}$", clean_name.replace(" ", "")):
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


# ── Upload handler ──
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".webm", ".amr"}


async def handle_upload(file, file_type: str = None):
    """Handle multi-modal file uploads from Mini Program."""
    _, _, _, _, UPLOAD_DIR = _get_paths()
    ext = os.path.splitext(file.filename or "")[1].lower()
    original_filename = file.filename or "unknown"
    if file_type == "audio" or ext in ALLOWED_AUDIO_EXTENSIONS:
        media_type, allowed = "audio", ALLOWED_AUDIO_EXTENSIONS
    elif file_type == "image" or ext in ALLOWED_IMAGE_EXTENSIONS:
        media_type, allowed = "image", ALLOWED_IMAGE_EXTENSIONS
    else:
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            media_type, allowed = "image", ALLOWED_IMAGE_EXTENSIONS
        elif ext in ALLOWED_AUDIO_EXTENSIONS:
            media_type, allowed = "audio", ALLOWED_AUDIO_EXTENSIONS
        elif ext in (".txt", ".md", ".csv", ".json", ".log"):
            media_type, allowed = "text", {".txt", ".md", ".csv", ".json", ".log"}
        else:
            return {"status": "error", "message": f"不支持的文件类型: {ext}"}
    if ext not in allowed:
        return {"status": "error", "message": f"不支持的{media_type}格式: {ext}"}
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
    except Exception as e:
        return {"status": "error", "message": f"保存文件失败: {str(e)}"}
    file_url = f"/uploads/{unique_name}"
    if media_type == "image":
        extracted_text = _extract_image_description(save_path, original_filename)
    elif media_type == "audio":
        extracted_text = _extract_audio_transcription(save_path, original_filename)
    elif media_type == "text":
        extracted_text = _extract_text_content(save_path)
    else:
        extracted_text = f"[{media_type}] 文件已保存: {original_filename}"
    extracted_data = _ingestor_extract_keywords(extracted_text)
    keywords = extracted_data.get("keywords", [])
    intent = extracted_data.get("intent", "未知")
    topics = extracted_data.get("topics", [])
    routing_result = {"status": "unmatched", "message": "未找到匹配的 Agent"}
    routed_to = None
    agent_info = None
    dispatcher = _create_dispatcher()
    if dispatcher is not None:
        try:
            routing_result = dispatcher.route(keywords)
        except Exception as e:
            routing_result = {"status": "error", "message": f"Dispatcher 路由失败: {str(e)}"}
    if routing_result.get("status") == "routed":
        agent = routing_result.get("agent", {})
        routed_to = agent.get("name", "Unknown")
        agent_info = {"name": routed_to, "id": agent.get("id", "unknown"),
                       "description": agent.get("description", ""), "tags": agent.get("tags", [])}
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
    return {
        "status": "success", "file_url": file_url, "file_path": save_path,
        "type": media_type, "filename": original_filename, "extracted_text": extracted_text,
        "routed_to": routed_to, "agent": agent_info,
        "extracted_data": {"keywords": keywords, "intent": intent, "topics": topics},
    }
