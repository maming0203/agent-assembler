"""P5.1 路由聚合 — 拆分后的子模块组合。

所有端点按功能拆为 4 个文件（均 <300 行）：
- routes_recipes.py   — Recipe CRUD (6 端点)
- routes_apikeys.py   — API Key 管理 (3 端点)
- routes_metrics.py   — Metrics/Analytics (3 端点)
- routes_deploy.py    — Deploy 发布 (3 端点)
"""
from .routes_recipes import router as recipes_router, RECIPE_BASE
from .routes_apikeys import router as apikeys_router
from .routes_metrics import router as metrics_router
from .routes_deploy import router as deploy_router

# 聚合所有路由器（供 core.py 注册）
all_routers = [recipes_router, apikeys_router, metrics_router, deploy_router]
