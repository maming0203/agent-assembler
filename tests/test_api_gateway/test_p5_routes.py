"""测试 P5.1 Gateway 新增端点。"""

import pytest
import json
from fastapi.testclient import TestClient

# Ensure src is in path for SDK imports
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api_gateway.core import app

client = TestClient(app)


# ──────────────────────────────────────────
# Recipe CRUD
# ──────────────────────────────────────────

def test_list_recipes():
    """列出所有配方。"""
    resp = client.get("/api/v1/recipes")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "recipes" in data

def test_search_recipes():
    """搜索配方。"""
    resp = client.get("/api/v1/recipes/search?q=test")
    assert resp.status_code == 200
    data = resp.json()
    assert "matches" in data
    assert "recipes" in data

def test_get_recipe_not_found():
    """获取不存在的配方 → 404。"""
    resp = client.get("/api/v1/recipes/nonexistent-recipe-xyz")
    assert resp.status_code == 404

def test_create_recipe():
    """创建新配方。"""
    import tempfile, os
    from api_gateway.config import RECIPE_BASE

    # 创建临时目录用于测试
    test_dir = tempfile.mkdtemp()
    original = RECIPE_BASE

    # 用临时目录替换
    from api_gateway import config
    config.RECIPE_BASE = test_dir

    # Patch routes_recipes module-level RECIPE_BASE (where _load_recipes reads from)
    from api_gateway import routes_recipes
    routes_recipes.RECIPE_BASE = test_dir

    resp = client.post("/api/v1/recipes", json={
        "name": "test-recipe-p5",
        "trigger_keywords": ["test", "p5"],
        "skills": [],
        "notes": "P5 测试配方",
    })

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "created"
    assert data["name"] == "test-recipe-p5"

    # 清理
    config.RECIPE_BASE = original
    routes_recipes.RECIPE_BASE = original

def test_get_created_recipe():
    """获取刚创建的配方。"""
    import tempfile, os
    from api_gateway import config
    from api_gateway import routes_recipes

    test_dir = tempfile.mkdtemp()
    original = config.RECIPE_BASE
    config.RECIPE_BASE = test_dir
    routes_recipes.RECIPE_BASE = test_dir

    # 先创建
    client.post("/api/v1/recipes", json={
        "name": "test-get-recipe",
        "trigger_keywords": ["get"],
        "skills": [],
        "notes": "test",
    })

    # 再获取
    resp = client.get("/api/v1/recipes/test-get-recipe")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-get-recipe"

    config.RECIPE_BASE = original
    routes_recipes.RECIPE_BASE = original


# ──────────────────────────────────────────
# API Key 管理
# ──────────────────────────────────────────

def test_create_api_key():
    """创建 API Key。"""
    resp = client.post("/api/v1/apikeys", json={
        "name": "test-key",
        "plan": "free",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "created"
    assert data["key"].startswith("sk-")
    assert data["plan"] == "free"

def test_list_api_keys():
    """列出 API Keys。"""
    # 先创建一个
    client.post("/api/v1/apikeys", json={"name": "list-test", "plan": "free"})

    resp = client.get("/api/v1/apikeys")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "keys" in data

def test_revoke_api_key():
    """撤销 API Key。"""
    # 创建
    resp = client.post("/api/v1/apikeys", json={"name": "revoke-test", "plan": "free"})
    key = resp.json()["key"]
    prefix = key[:8]

    # 撤销
    resp = client.delete(f"/api/v1/apikeys/{prefix}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"

    # 再撤销 → 404
    resp = client.delete(f"/api/v1/apikeys/{prefix}")
    assert resp.status_code == 404


# ──────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────

def test_get_metrics():
    """获取指标。"""
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_runs" in data
    assert "users" in data
    assert "top_users" in data

def test_get_metrics_summary():
    """获取汇总指标。"""
    resp = client.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_runs" in data
    assert "active_recipes" in data


# ──────────────────────────────────────────
# Deploy
# ──────────────────────────────────────────

def test_deploy_coze_no_key():
    """无 API Key → 401。"""
    resp = client.post("/api/v1/deploy/coze", json={
        "name": "test",
        "description": "test",
        "platform": "Coze",
    })
    assert resp.status_code == 401

def test_deploy_coze_invalid_key():
    """无效 API Key → 403。"""
    resp = client.post("/api/v1/deploy/coze", json={
        "name": "test",
        "description": "test",
        "platform": "Coze",
    }, headers={"x-api-key": "sk-invalid"})
    assert resp.status_code == 403

def test_deploy_qianwen_no_key():
    """无 API Key → 401。"""
    resp = client.post("/api/v1/deploy/qianwen", json={
        "name": "test",
        "description": "test",
        "platform": "Qianwen",
    })
    assert resp.status_code == 401
