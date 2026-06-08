"""Metrics / Analytics 端点 — 从 p5_routes.py 拆分。"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header

from .db import load_json
from .config import USAGE_FILE, DB_FILE
from .routes_recipes import _load_recipes

router = APIRouter(prefix="/api/v1", tags=["metrics"])


@router.get("/metrics")
async def get_metrics(limit: int = 50, x_api_key: str = Header(None)):
    usage = load_json(USAGE_FILE) if os.path.exists(USAGE_FILE) else {}
    total_runs = sum(v.get("count", 0) if isinstance(v, dict) else v for v in usage.values())
    return {
        "total_runs": total_runs,
        "users": len(usage),
        "top_users": sorted(
            [{"user": k, "runs": v.get("count", 0) if isinstance(v, dict) else v}
             for k, v in usage.items()],
            key=lambda x: x["runs"], reverse=True,
        )[:limit],
    }

@router.get("/metrics/summary")
async def get_metrics_summary(x_api_key: str = Header(None)):
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
    usage = load_json(USAGE_FILE) if os.path.exists(USAGE_FILE) else {}
    data_points = []
    for uid, info in usage.items():
        count = info.get("count", 0) if isinstance(info, dict) else info
        data_points.append({"user": uid, "runs": count})
    return {"days": days, "total": sum(d["runs"] for d in data_points), "data": data_points}
