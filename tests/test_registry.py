"""测试 RecipeRegistry — 配方市场基础结构"""

import json
import os
import tempfile
import pytest
from agent_assembler.registry import RecipeRegistry, RecipeVersion


SAMPLE_RECIPE = {
    "name": "财务分析",
    "trigger_keywords": ["财务报表", "利润分析", "成本核算"],
    "skills": ["profit_calc"],
    "notes": "用于零售商户的财务分析场景",
    "tags": ["finance", "retail"],
}

SAMPLE_RECIPE_2 = {
    "name": "合规检查",
    "trigger_keywords": ["合规审查", "合同审核", "法律风险"],
    "skills": ["compliance_check"],
    "notes": "自动合同合规性审查",
    "tags": ["legal", "compliance"],
}

SAMPLE_RECIPE_3 = {
    "name": "销售预测",
    "trigger_keywords": ["销售预测", "趋势分析", "数据建模"],
    "skills": ["sales_forecast"],
    "notes": "基于历史数据的销售趋势预测",
    "tags": ["data", "sales"],
}


# --- 注册与列出 ---

def test_register_and_list():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    assert reg.count() == 1
    assert reg.get("财务分析") is not None


def test_list_all_recipes():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    reg.register(SAMPLE_RECIPE_2)
    results = reg.list_recipes()
    assert len(results) == 2


def test_list_by_tag():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    reg.register(SAMPLE_RECIPE_2)
    results = reg.list_recipes(tag="finance")
    assert len(results) == 1
    assert results[0]["name"] == "财务分析"


def test_remove_recipe():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    assert reg.remove("财务分析") is True
    assert reg.count() == 0
    assert reg.remove("不存在的") is False


def test_remove_cleans_indices():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    reg.remove("财务分析")
    # 关键词索引中不应再有该配方
    for kw in SAMPLE_RECIPE["trigger_keywords"]:
        if kw.lower() in reg._keyword_index:
            assert "财务分析" not in reg._keyword_index[kw.lower()]


# --- 搜索（加权匹配）---

def test_search_exact_name_match():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    results = reg.search("财务分析")
    assert len(results) == 1
    assert results[0]["recipe"]["name"] == "财务分析"
    assert results[0]["score"] >= 100


def test_search_keyword_match():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    results = reg.search("财务报表")
    assert len(results) == 1
    assert results[0]["score"] >= 10


def test_search_partial_match():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    results = reg.search("财务")
    assert len(results) == 1
    assert results[0]["score"] > 0


def test_search_no_match():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    results = reg.search("完全不相关的内容")
    assert len(results) == 0


def test_search_ranking():
    """测试搜索结果按分数排序"""
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    reg.register(SAMPLE_RECIPE_2)
    reg.register(SAMPLE_RECIPE_3)
    results = reg.search("财务")
    assert len(results) >= 1
    # 财务分析应该排第一
    assert results[0]["recipe"]["name"] == "财务分析"


def test_search_top_k():
    reg = RecipeRegistry()
    for r in [SAMPLE_RECIPE, SAMPLE_RECIPE_2, SAMPLE_RECIPE_3]:
        reg.register(r)
    results = reg.search("分析", top_k=2)
    assert len(results) <= 2


# --- 导入导出 ---

def test_export_single_recipe():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = reg.export_recipe("财务分析", tmpdir)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["name"] == "财务分析"


def test_export_recipe_not_found():
    reg = RecipeRegistry()
    with pytest.raises(KeyError):
        reg.export_recipe("不存在的", "/tmp")


def test_import_single_recipe():
    reg = RecipeRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.json")
        with open(path, "w") as f:
            json.dump(SAMPLE_RECIPE, f)
        name = reg.import_recipe(path)
        assert name == "财务分析"
        assert reg.count() == 1


def test_export_all():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    reg.register(SAMPLE_RECIPE_2)
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = reg.export_all(tmpdir)
        assert len(paths) == 2
        for p in paths:
            assert os.path.exists(p)


def test_import_directory():
    reg = RecipeRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        for r in [SAMPLE_RECIPE, SAMPLE_RECIPE_2]:
            path = os.path.join(tmpdir, f'{r["name"]}.json')
            with open(path, "w") as f:
                json.dump(r, f)
        count = reg.import_directory(tmpdir)
        assert count == 2
        assert reg.count() == 2


# --- JSON 序列化 ---

def test_to_dict_and_from_json():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "registry.json")
        reg.to_json(path)
        reg2 = RecipeRegistry.from_json(path)
        assert reg2.count() == 1
        assert reg2.get("财务分析") is not None


# --- 扫描目录 ---

def test_scan_directory():
    reg = RecipeRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        for r in [SAMPLE_RECIPE, SAMPLE_RECIPE_2]:
            path = os.path.join(tmpdir, f'{r["name"]}.json')
            with open(path, "w") as f:
                json.dump(r, f)
        reg = RecipeRegistry(registry_dir=tmpdir)
        count = reg.scan()
        assert count == 2
        assert reg.count() == 2


# --- RecipeVersion ---

def test_recipe_version_to_dict():
    v = RecipeVersion(
        version="1.0.0",
        author="Gino",
        created_at="2026-06-08",
        changelog="Initial release",
    )
    d = v.to_dict()
    assert d["version"] == "1.0.0"
    assert d["author"] == "Gino"


def test_recipe_version_from_dict():
    v = RecipeVersion.from_dict({
        "version": "0.2.0",
        "author": "Hermes",
        "created_at": "2026-06-08",
        "changelog": "Bug fixes",
        "file_path": "/some/path",
    })
    assert v.version == "0.2.0"
    assert v.author == "Hermes"


# --- repr ---

def test_registry_repr():
    reg = RecipeRegistry()
    reg.register(SAMPLE_RECIPE)
    assert "RecipeRegistry(count=1" in repr(reg)
