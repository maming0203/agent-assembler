"""Tests for Agent Assembler Adapters."""
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from agent_assembler.recipe import Recipe
from agent_assembler.adapters import CozeAdapter, QianwenAdapter


def test_coze_export_basic():
    """Test: CozeAdapter exports valid DSL structure."""
    recipe = Recipe(
        name="数据分析助手",
        trigger_keywords=["数据分析", "excel"],
        skills=[],
        notes="专门处理 Excel 数据分析任务"
    )
    
    adapter = CozeAdapter()
    result = adapter.export(recipe)
    
    assert "bot_info" in result
    assert result["bot_info"]["name"] == "数据分析助手"
    assert result["bot_info"]["prompt_info"]["prompt"] != ""
    assert result["model_info"]["model_name"] == "gpt-4o"
    assert result["metadata"]["source"] == "agent-assembler"
    print("✅ test_coze_export_basic passed")


def test_coze_skills_injection():
    """Test: CozeAdapter injects skill content into prompt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data_clean"))
        with open(os.path.join(tmpdir, "data_clean", "SKILL.md"), "w") as f:
            f.write("# 数据清洗\n步骤: 1. 去重 2. 格式化 3. 校验")
        
        recipe = Recipe(
            name="数据处理",
            trigger_keywords=["数据"],
            skills=["data_clean"]
        )
        
        adapter = CozeAdapter(skills_dir=tmpdir)
        result = adapter.export(recipe)
        prompt = result["bot_info"]["prompt_info"]["prompt"]
        
        assert "数据清洗" in prompt
        assert "去重" in prompt
        print("✅ test_coze_skills_injection passed")


def test_coze_validate():
    """Test: CozeAdapter validates recipe constraints."""
    adapter = CozeAdapter()
    
    # Valid recipe
    good = Recipe(name="短名", trigger_keywords=["test"], skills=[])
    assert len(adapter.validate(good)) == 0
    
    # Name too long
    long_name = Recipe(name="A" * 51, trigger_keywords=["test"], skills=[])
    errors = adapter.validate(long_name)
    assert len(errors) > 0
    assert "50" in errors[0]
    
    print("✅ test_coze_validate passed")


def test_qianwen_export_basic():
    """Test: QianwenAdapter exports valid DSL structure."""
    recipe = Recipe(
        name="客服助手",
        trigger_keywords=["客服", "咨询"],
        notes="处理客户咨询和投诉",
        routing="operations-venue-agent"
    )
    
    adapter = QianwenAdapter()
    result = adapter.export(recipe)
    
    assert "name" in result
    assert result["name"] == "客服助手"
    assert "system_prompt" in result
    assert result["model"] == "qwen-max"
    assert result["metadata"]["routing"] == "operations-venue-agent"
    print("✅ test_qianwen_export_basic passed")


def test_qianwen_skills_injection():
    """Test: QianwenAdapter injects skill content into prompt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "reply_template"))
        with open(os.path.join(tmpdir, "reply_template", "SKILL.md"), "w") as f:
            f.write("# 回复模板\n规范: 礼貌、专业、简洁")
        
        recipe = Recipe(
            name="智能客服",
            trigger_keywords=["回复"],
            skills=["reply_template"]
        )
        
        adapter = QianwenAdapter(skills_dir=tmpdir)
        result = adapter.export(recipe)
        prompt = result["system_prompt"]
        
        assert "回复模板" in prompt
        assert "礼貌" in prompt
        print("✅ test_qianwen_skills_injection passed")


def test_qianwen_validate():
    """Test: QianwenAdapter validates recipe constraints."""
    adapter = QianwenAdapter()
    
    # Valid recipe
    good = Recipe(name="正常名", trigger_keywords=["test"], skills=[])
    assert len(adapter.validate(good)) == 0
    
    # Name too long (30 char limit for Qianwen)
    long_name = Recipe(name="A" * 31, trigger_keywords=["test"], skills=[])
    errors = adapter.validate(long_name)
    assert len(errors) > 0
    assert "30" in errors[0]
    
    print("✅ test_qianwen_validate passed")


def test_adapter_missing_skill_warning():
    """Test: Adapter handles missing skill gracefully."""
    recipe = Recipe(
        name="测试",
        trigger_keywords=["test"],
        skills=["nonexistent_skill"]
    )
    
    coze = CozeAdapter(skills_dir="/tmp")
    result = coze.export(recipe)
    assert "nonexistent_skill" in result["bot_info"]["prompt_info"]["prompt"]
    assert "not found" in result["bot_info"]["prompt_info"]["prompt"]
    
    qianwen = QianwenAdapter(skills_dir="/tmp")
    result = qianwen.export(recipe)
    assert "nonexistent_skill" in result["system_prompt"]
    assert "未找到" in result["system_prompt"]
    
    print("✅ test_adapter_missing_skill_warning passed")


if __name__ == "__main__":
    test_coze_export_basic()
    test_coze_skills_injection()
    test_coze_validate()
    test_qianwen_export_basic()
    test_qianwen_skills_injection()
    test_qianwen_validate()
    test_adapter_missing_skill_warning()
    print("\n✅ All 7 adapter tests passed")
