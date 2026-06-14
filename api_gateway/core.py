"""Core Gateway module — FastAPI app, routes, DB ops, recipe matching, usage tracking."""
import json
import os
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from .autocraft_v4 import auto_craft_and_run, sanitize
from .config import (
    AUTO_DIR, DISPATCHER_SCRIPT, INGESTOR_SCRIPT, IS_CLOUD,
    MANIFESTS_DIR, RECIPE_BASE, ROUTING_SCHEMA_PATH, SKILL_BASE,
    SKILL_AUTO_DIR, UPLOAD_DIR, DB_FILE, USAGE_FILE,
    AUTOCRAFT_REF_DIR, RECIPE_SCHEMA_PATH, SCRIPT_DIRS,
)
from .db import (
    check_usage, find_recipe, find_skill_in_directory, load_infrastructure_skills,
    get_user_id_by_key, increment_usage, is_premium,
    load_json, load_skill, paywall_response, save_json,
)
from .multimodal import handle_upload, _ingestor_extract_keywords, _create_dispatcher
from .script_engine import _extract_script_args, _run_script, _run_script_json

# App
app = FastAPI(title="Agent Assembler Gateway", version="2.1.0")

# P5 Routes
from .p5_routes import all_routers
for _r in all_routers:
    app.include_router(_r)

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


def call_agent(routing_id, msg):
    """Direct LLM call — decoupled from OpenClaw. Uses routing_id to select system prompt."""
    system_prompt = _load_agent_system_prompt(routing_id)
    if not system_prompt:
        # Fallback: use routing_id as role hint
        system_prompt = f"You are a specialized assistant for {routing_id}. Provide expert, actionable advice."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": msg},
    ]
    return _call_llm(messages)


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
            # If LLM fails but we have script output, return script result directly
            if llm_response.startswith("LLM call failed:") and 'success' in script_output:
                try:
                    script_data = json.loads(script_output)
                    if script_data.get("status") == "success":
                        # Format script output as readable report
                        output = script_data.get("output", {})
                        steps = script_data.get("steps", [])
                        report_lines = []
                        if isinstance(output, dict):
                            for k, v in output.items():
                                report_lines.append(f"- {k}: {v}")
                        if steps:
                            report_lines.append("\n计算步骤:")
                            for s in steps:
                                report_lines.append(f"  {s}")
                        llm_response = "\n".join(report_lines) if report_lines else script_output
                except (json.JSONDecodeError, AttributeError):
                    pass  # Keep the LLM error message
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
            infra = load_infrastructure_skills()
            if infra:
                skill_content = infra + "\n\n" + skill_content
            agent_query = (
                f"You are an assistant. A calculation/processing tool has produced the following result.\n"
                f"Strictly follow this skill logic for context:\n{skill_content}\n\n"
                f"TOOL OUTPUT:\n{script_output}\n\n"
                f"User Query: {req.query}\n\n"
                f"Explain this result to the user in a clear, professional manner. "
                f"Do NOT recalculate."
            )
            # Store script_output for fallback if LLM fails
            _last_script_output = script_output
        else:
            print(f"[Script Engine] Script failed, falling back to LLM: {script_output}")
            skill_content = load_skill(recipe)
            infra = load_infrastructure_skills()
            if infra:
                skill_content = infra + "\n\n" + skill_content
            agent_query = (
                f"Strictly follow this skill logic:\n{skill_content}\n\n"
                f"User Query: {req.query}\n\n"
                f"Note: Script failed: {script_output}. Please answer using your knowledge."
            )
    else:
        skill_content = load_skill(recipe)
        infra = load_infrastructure_skills()
        if infra:
            skill_content = infra + "\n\n" + skill_content
        agent_query = f"Strictly follow this skill logic:\n{skill_content}\n\nUser Query: {req.query}"
    routing_id = recipe.get("routing", {}).get("agent_id", "") if isinstance(recipe.get("routing"), dict) else recipe.get("routing", "")
    if not routing_id:
        routing_id = "general"
    result = call_agent(routing_id, agent_query)
    # Fallback: if LLM fails but script succeeded, return script output directly
    if isinstance(result, str) and result.startswith("LLM call failed:") and script_path and 'success' in str(script_output):
        try:
            script_data = json.loads(script_output)
            if script_data.get("status") == "success":
                output = script_data.get("output", {})
                steps = script_data.get("steps", [])
                report_lines = ["📊 计算结果:"]
                if isinstance(output, dict):
                    for k, v in output.items():
                        report_lines.append(f"  • {k}: {v}")
                if steps:
                    report_lines.append("\n📝 计算步骤:")
                    for s in steps:
                        report_lines.append(f"  {s}")
                data_info = script_data.get("data", {})
                if data_info:
                    report_lines.append("\n📋 输入参数:")
                    for k, v in data_info.items():
                        if k != "query":
                            report_lines.append(f"  • {k}: {v}")
                result = "\n".join(report_lines)
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass  # Keep the LLM error message
    return {"status": "success", "recipe_used": recipe.get("name", recipe.get("filename", "unknown")), "report": result}




class ExecuteRequest(BaseModel):
    query: str
    inputs: Optional[dict] = None


@app.post("/api/v1/execute")
async def execute_recipe(req: ExecuteRequest, x_api_key: str = Header(None)):
    """Execute a matched recipe's script and return structured calculation results.

    1. Match query to a recipe
    2. Extract/merge inputs from request + recipe defaults + query parsing
    3. Execute script with --json mode
    4. Return structured result with contract/result fields
    """
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")

    user_id = get_user_id_by_key(x_api_key)
    if not user_id:
        raise HTTPException(403, "Invalid Key")

    db = load_json(DB_FILE)
    user_info = db.get(user_id, {})
    user_plan = user_info.get("plan", "free") if isinstance(user_info, dict) else "free"

    # 1. Find matching recipe
    recipe = find_recipe(req.query)
    if not recipe:
        return {
            "status": "not_found",
            "message": "未找到匹配的配方",
            "query": req.query,
        }

    # 2. Premium / usage checks
    if is_premium(recipe) and user_plan == "free":
        return paywall_response("Premium 配方需要升级解锁。")
    if user_plan == "free":
        if check_usage(user_id) >= 3:
            return paywall_response("今日免费额度已用完。")
    increment_usage(user_id)

    # 3. Get script path
    script_path = recipe.get("script_path") or recipe.get("script") or recipe.get("code")
    if not script_path:
        return {
            "status": "error",
            "message": "该配方没有关联的执行脚本",
            "recipe": recipe.get("name", recipe.get("filename", "unknown")),
        }

    # 4. Build inputs: merge request inputs + recipe defaults + query parsing
    inputs = {}

    # Start with any explicit inputs from the request
    if req.inputs:
        inputs.update(req.inputs)

    # Add recipe default script_args
    recipe_args = recipe.get("script_args", {})
    if isinstance(recipe_args, dict):
        for k, v in recipe_args.items():
            if k not in inputs:
                inputs[k] = v

    # Parse key=value from query
    import re as _re
    for match in _re.findall(r'(\w+)\s*[=:]\s*([^\s,;]+)', req.query):
        key, val = match
        if key not in inputs:
            try:
                inputs[key] = float(val) if '.' in val else int(val)
            except ValueError:
                inputs[key] = val

    # 5. Execute script with --json mode
    success, output = _run_script_json(script_path, inputs)

    if not success:
        return {
            "status": "script_error",
            "message": output,
            "recipe": recipe.get("name", recipe.get("filename", "unknown")),
            "script": script_path,
            "inputs": inputs,
        }

    # 6. Parse and return structured result
    try:
        result_data = json.loads(output)
    except json.JSONDecodeError:
        return {
            "status": "parse_error",
            "message": "脚本输出格式异常",
            "raw_output": output[:500],
            "recipe": recipe.get("name", recipe.get("filename", "unknown")),
        }

    # Build response with contract structure
    data = result_data.get("data", {})
    return {
        "status": "success",
        "recipe": recipe.get("name", recipe.get("filename", "unknown")),
        "slug": recipe.get("slug", recipe.get("filename", "")),
        "contract": {
            "inputs_summary": result_data.get("meta", {}).get("inputs_summary", inputs),
            "result": {
                "monthly_fixed_cost": data.get("monthly_fixed_cost"),
                "profit_per_order": data.get("profit_per_order"),
                "monthly_break_even_orders": data.get("monthly_break_even_orders"),
                "daily_break_even_orders": data.get("daily_break_even_orders"),
                "daily_break_even_revenue": data.get("daily_break_even_revenue"),
                "monthly_break_even_revenue": data.get("monthly_break_even_revenue"),
                "cost_structure": data.get("cost_structure"),
                "profit_scenarios": data.get("profit_scenarios"),
                "forecast_table": [
                    {
                        "label": s["label"],
                        "daily_orders": s["daily_orders"],
                        "monthly_orders": s["monthly_orders"],
                        "monthly_revenue": s["monthly_revenue"],
                        "monthly_net_profit": s["monthly_net_profit"],
                        "is_profitable": s["is_profitable"],
                    }
                    for s in data.get("profit_scenarios", [])
                ],
                "suggestions": data.get("suggestions", []),
                "breakEvenOrders": data.get("daily_break_even_orders"),
                "forecastTable": [
                    {
                        "label": s["label"],
                        "dailyOrders": s["daily_orders"],
                        "monthlyRevenue": s["monthly_revenue"],
                        "monthlyNetProfit": s["monthly_net_profit"],
                        "isProfitable": s["is_profitable"],
                    }
                    for s in data.get("profit_scenarios", [])
                ],
            },
        },
        "meta": result_data.get("meta", {}),
    }




# ─────────────────────────────────────────────────────────────
# /api/v1/calc — 快速计算端点（脚本直出，不调 LLM）
# ─────────────────────────────────────────────────────────────

class CalcRequest(BaseModel):
    query: str
    inputs: Optional[dict] = None


# 各配方的默认参数（防止必填参数缺失报错）
_CALC_DEFAULTS = {
    # 保本点计算参数
    "rent": 0,
    "utilities": 500,
    "labor": 0,
    "other": 0,
    "other_fixed": 0,
    "gross_margin": 50,
    "unit_price": 15,
    "unit_cost": 0,
    # 美容院配方参数
    "avg_ticket": 300,
    "monthly_visits": 2,
    "target_cashflow": 50000,
    "max_gift_rate": 30,
    "base_salary": 2000,
    "manual_fee_per_service": 30,
    "total_services": 80,
    "total_revenue": 24000,
    "commission_rate": 10,
    "tier_bonus_threshold": 100,
    "tier_bonus_per_service": 10,
    "product_cost": 30,
    "labor_hours": 1.5,
    "hourly_labor_cost": 50,
    "target_margin": 60,
    "overhead_rate": 20,
}


@app.post("/api/v1/calc")
async def calc_recipe(req: CalcRequest, x_api_key: str = Header(None)):
    """快速计算端点 — 脚本直出结构化结果，不调 LLM。

    与 /api/v1/execute 的区别：
    1. 参数有默认值（不会因缺少必填参数报错）
    2. 无配方时快速失败（不触发 AutoCraft）
    3. 响应时间 < 3 秒（纯脚本执行）
    """
    if not x_api_key:
        raise HTTPException(401, "Missing API Key")

    user_id = get_user_id_by_key(x_api_key)
    if not user_id:
        raise HTTPException(403, "Invalid Key")

    # 1. 匹配配方（无匹配则快速失败）
    recipe = find_recipe(req.query)
    if not recipe:
        return {
            "status": "not_found",
            "message": "未找到匹配的配方，请换个问法",
            "query": req.query,
        }

    # 2. 配额检查
    db = load_json(DB_FILE)
    user_info = db.get(user_id, {})
    user_plan = user_info.get("plan", "free") if isinstance(user_info, dict) else "free"

    if is_premium(recipe) and user_plan == "free":
        return paywall_response("Premium 配方需要升级解锁。")
    if user_plan == "free":
        if check_usage(user_id) >= 3:
            return paywall_response("今日免费额度已用完。")
    increment_usage(user_id)

    # 3. 获取脚本路径
    script_path = recipe.get("script_path") or recipe.get("script") or recipe.get("code")
    if not script_path:
        return {
            "status": "error",
            "message": "该配方没有关联的执行脚本",
            "recipe": recipe.get("name", recipe.get("filename", "unknown")),
        }

    # 4. 构建参数：默认值 → 配方默认 → 请求参数 → 查询解析
    inputs = dict(_CALC_DEFAULTS)  # 先填默认值

    recipe_args = recipe.get("script_args", {})
    if isinstance(recipe_args, dict):
        inputs.update(recipe_args)

    if req.inputs:
        inputs.update(req.inputs)

    # 从查询中解析参数（中文模式：房租5000）
    import re as _re
    chinese_key_map = {
        # 保本点计算
        "房租": "rent", "租金": "rent", "房租费": "rent",
        "水电": "utilities", "水电费": "utilities", "水电气": "utilities",
        "人工": "labor", "人工费": "labor", "工资": "labor", "薪资": "labor",
        "毛利": "gross_margin", "毛利率": "gross_margin",
        "售价": "unit_price", "单价": "unit_price",
        "成本": "unit_cost", "进价": "unit_cost",
        "其他": "other_fixed", "其他固定": "other_fixed", "其他成本": "other_fixed",
        # 美容院配方
        "客单价": "avg_ticket", "均价": "avg_ticket",
        "到店": "monthly_visits", "月到店": "monthly_visits",
        "充值": "target_cashflow", "目标": "target_cashflow",
        "赠送": "max_gift_rate", "赠送比例": "max_gift_rate",
        "底薪": "base_salary",
        "手工费": "manual_fee_per_service",
        "服务次数": "total_services", "次数": "total_services",
        "业绩": "total_revenue",
        "提成": "commission_rate", "提成比例": "commission_rate",
        "产品成本": "product_cost",
        "工时": "labor_hours",
        "时薪": "hourly_labor_cost",
        "利润率": "target_margin",
    }
    for match in _re.findall(r"([\u4e00-\u9fff]+)\s*(\d+(?:\.\d+)?)", req.query):
        cn_key, num_val = match
        if cn_key in chinese_key_map:
            eng_key = chinese_key_map[cn_key]
            val = float(num_val)
            # gross_margin 保持百分比（50 表示 50%）
            inputs[eng_key] = val

    # 英文模式：key=value
    for match in _re.findall(r"(\w+)\s*[=:]\s*([^\s,;]+)", req.query):
        key, val = match
        if key not in inputs or inputs[key] == _CALC_DEFAULTS.get(key):
            try:
                inputs[key] = float(val) if "." in val else int(val)
            except ValueError:
                inputs[key] = val

    inputs["query"] = req.query
    
    # 特殊处理：广告合规检测需要 ad_text 参数
    if "ad_compliance" in script_path or "ad-compliance" in script_path:
        inputs["ad_text"] = req.query

    # 5. 执行脚本
    success, output = _run_script_json(script_path, inputs)

    if not success:
        return {
            "status": "script_error",
            "message": output,
            "recipe": recipe.get("name", recipe.get("filename", "unknown")),
            "inputs": inputs,
        }

    # 6. 返回结构化结果
    try:
        result_data = json.loads(output)
    except json.JSONDecodeError:
        return {
            "status": "parse_error",
            "message": "脚本输出格式异常",
            "raw_output": output[:500],
        }

    data = result_data.get("data", {})
    return {
        "status": "success",
        "recipe": recipe.get("name", recipe.get("filename", "unknown")),
        "slug": recipe.get("slug", recipe.get("filename", "")),
        "data": data,
        "meta": result_data.get("meta", {}),
        "inputs": {k: v for k, v in inputs.items() if k != "query"},
    }


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
