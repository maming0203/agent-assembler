"""Agent Assembler — 三位一体执行路由 (Trinity Execution) + 工作流引擎
匹配配方 -> 加载技能 -> 执行计算/脚本 -> 返回纯契约 JSON
工作流: DAG 执行引擎，支持串行/并行/条件分支/数据流传递/异常处理
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import sys
from typing import Optional, List, Dict, Any

# 路径设置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPE_BASE = os.path.join(BASE_DIR, "recipes")
SKILL_BASE = os.path.join(BASE_DIR, "skills")

router = APIRouter(prefix="/api/v1", tags=["trinity"])

# ── 工作流引擎 ──
from .workflow_engine import WorkflowEngine

workflow_engine = WorkflowEngine()

# ═══════════════════════════════════════════════════
# 计算引擎集成 (lunar_python)
# ═══════════════════════════════════════════════════
# 将 ECS 的 lunar_python 目录加入路径
LP_PATH = os.path.join(BASE_DIR, "lunar_python")
if LP_PATH not in sys.path:
    sys.path.insert(0, LP_PATH)

try:
    from lunar_python import Solar, Lunar
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False
    print("[Trinity] Warning: lunar_python not found. Calculation will fail.")


class ExecuteRequest(BaseModel):
    query: str
    action: str = "run"
    params: Optional[Dict[str, Any]] = None

def _load_recipes() -> list:
    recipes = []
    if not os.path.exists(RECIPE_BASE): return recipes
    for root, _, files in os.walk(RECIPE_BASE):
        for f in files:
            if f.endswith(".json") and f != "README.md":
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    data["_file"] = f
                    recipes.append(data)
                except: continue
    return recipes

def _match_recipe(query: str) -> dict:
    q = query.lower()
    for r in _load_recipes():
        keywords = [k.lower() for k in r.get("trigger_keywords", [])]
        name = r.get("name", "").lower()
        notes = r.get("notes", "").lower()
        if name in q or any(k in q for k in keywords) or any(k in q for k in notes.split()):
            return r
    return None

def _build_contract(recipe: dict, query: str, calc_result: dict) -> dict:
    return {
        "status": "matched",
        "recipe": recipe.get("name", "Unknown"),
        "contract": {
            "render_type": calc_result.get("render_type", "text_card"),
            "title": calc_result.get("title", recipe.get("name")),
            "summary": calc_result.get("summary", "执行成功"),
            "data": calc_result.get("data", {}),
            "actions": calc_result.get("actions", [])
        }
    }

# ── 计算逻辑 ──
def _compute_bazi(year, month, day, hour=12, gender=1):
    if not HAS_LUNAR: return {"error": "lunar-python missing"}
    solar = Solar.fromYmdHms(year, month, day, hour, 0, 0)
    ec = solar.getLunar().getEightChar()
    return {
        "render_type": "bazi_chart_card",
        "title": "八字排盘",
        "summary": f"{year}-{month}-{day} {hour}时 — 日主{ec.getDayGan()}，属{ec.getYearZhi()}",
        "data": {
            "pillars": {
                "year": {"full": ec.getYear()}, "month": {"full": ec.getMonth()},
                "day": {"full": ec.getDay()}, "hour": {"full": ec.getTime()}
            },
            "wuxing_count": {"木":0, "火":0, "土":0, "金":0, "水":0}, # Simplified for brevity
            "actions": [{"label": "五行分析", "intent": "wuxing"}]
        }
    }

@router.post("/execute")
async def execute_trinity(req: ExecuteRequest):
    if req.action in ["bazi_calc", "couple_analysis", "ziwei_calc"]:
        p = req.params or {}
        if req.action == "bazi_calc":
            res = _compute_bazi(p.get("year"), p.get("month"), p.get("day"), p.get("hour", 12))
            return res
    
    # 默认配方匹配流程
    recipe = _match_recipe(req.query)
    if not recipe:
        return {"status": "no_match", "message": f"未找到匹配配方：{req.query}"}
    
    # 这里可以扩展：如果配方有 script_path，执行脚本
    # 否则返回基本匹配结果
    return _build_contract(recipe, req.query, {
        "render_type": "bazi_chart_card",
        "title": recipe.get("name"),
        "summary": "已匹配配方，等待进一步操作",
        "actions": [{"label": "开始计算", "intent": "bazi_calc"}]
    })

@router.get("/skills/{recipe_name}")
async def get_skill(recipe_name: str):
    skill_path = os.path.join(SKILL_BASE, recipe_name, "SKILL.md")
    mcp_path = os.path.join(SKILL_BASE, recipe_name, "mcp.json")
    skill_md = ""
    mcp_json = {}
    if os.path.exists(skill_path):
        with open(skill_path, "r", encoding="utf-8") as f: skill_md = f.read()
    if os.path.exists(mcp_path):
        with open(mcp_path, "r", encoding="utf-8") as f: mcp_json = json.load(f)
    return {"skill": skill_md, "mcp": mcp_json}


# ═══════════════════════════════════════════════════
# 工作流引擎端点
# ═══════════════════════════════════════════════════

class WorkflowExecuteRequest(BaseModel):
    workflow_name: str
    inputs: Optional[Dict[str, Any]] = None


@router.post("/workflow/execute")
async def execute_workflow(req: WorkflowExecuteRequest, x_api_key: str = None):
    """Execute a workflow by name with optional user inputs.
    
    Request: {"workflow_name": "...", "inputs": {...}}
    Response: {"status": "completed|aborted|partial|error", "workflow": "...", "steps": {...}, ...}
    """
    if not req.workflow_name:
        raise HTTPException(400, "workflow_name is required")

    print(f"[Workflow] Executing workflow: {req.workflow_name} with inputs: {req.inputs}")
    result = workflow_engine.execute(req.workflow_name, req.inputs or {})
    return result


@router.get("/workflow/list")
async def list_workflows():
    """List all available workflows."""
    return {"workflows": workflow_engine.list_workflows()}


@router.get("/workflow/{workflow_name}")
async def get_workflow(workflow_name: str):
    """Get a workflow definition by name."""
    wf = workflow_engine.load_workflow(workflow_name)
    if not wf:
        raise HTTPException(404, f"Workflow '{workflow_name}' not found")
    return {"workflow": wf}
