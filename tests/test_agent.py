"""测试 Agent 类与 AgentSpec。"""

import pytest
from agent_assembler.agent import AgentSpec, Agent


# --- AgentSpec 验证 ---

def test_agent_spec_validate_ok():
    spec = AgentSpec(
        name="test-agent",
        role="测试角色",
        system_prompt="你是一个测试 Agent",
        recipes=["test-recipe"],
    )
    errors = spec.validate()
    assert errors == []


def test_agent_spec_validate_missing_name():
    spec = AgentSpec(
        name="",
        role="测试角色",
        system_prompt="你是一个测试 Agent",
        recipes=["test-recipe"],
    )
    errors = spec.validate()
    assert any("name is required" in e for e in errors)


def test_agent_spec_validate_empty_recipes_and_skills():
    spec = AgentSpec(
        name="test-agent",
        role="测试角色",
        system_prompt="你是一个测试 Agent",
    )
    errors = spec.validate()
    assert any("recipe or skill" in e for e in errors)


# --- Agent 侧车管理 ---

def test_agent_add_sidecar():
    spec = AgentSpec(name="t", role="r", system_prompt="s", skills=["x"])
    agent = Agent(spec)
    agent.add_sidecar("mock", object())
    assert "mock" in agent._sidecars


def test_agent_remove_sidecar():
    spec = AgentSpec(name="t", role="r", system_prompt="s", skills=["x"])
    agent = Agent(spec)
    agent.add_sidecar("mock", object())
    agent.remove_sidecar("mock")
    assert "mock" not in agent._sidecars


# --- Agent 执行 ---

def test_agent_run_basic():
    spec = AgentSpec(name="runner", role="r", system_prompt="s", skills=["x"])
    agent = Agent(spec)
    result = agent.run("hello")
    assert result["agent"] == "runner"
    assert result["query"] == "hello"
    assert result["processed_query"] == "hello"
    assert result["model"] == "qwen3.6-plus"


def test_agent_run_with_sidecar():
    spec = AgentSpec(name="runner", role="r", system_prompt="s", skills=["x"])
    agent = Agent(spec)

    class PreProcSidecar:
        def pre_process(self, query):
            return f"PREFIX: {query}"

    agent.add_sidecar("pre", PreProcSidecar())
    result = agent.run("hello")
    assert result["processed_query"] == "PREFIX: hello"
    assert "pre" in result["sidecars_active"]


# --- 历史记录 ---

def test_agent_history():
    spec = AgentSpec(name="h", role="r", system_prompt="s", skills=["x"])
    agent = Agent(spec)
    agent.run("q1")
    agent.run("q2")
    hist = agent.history
    assert len(hist) == 4  # user/assistant pairs × 2
    assert hist[0]["role"] == "user"
    assert hist[0]["content"] == "q1"
    assert hist[2]["content"] == "q2"
    # 返回的是副本，修改不影响内部状态
    hist.append({"role": "user", "content": "injected"})
    assert len(agent.history) == 4
