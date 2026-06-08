"""测试 P4.4 LLM 全链路集成。"""

import pytest
from agent_assembler.agent import AgentSpec, Agent
from agent_assembler.llm import LLMClient, LLMResponse
from agent_assembler.assembler import Assembler


# ──────────────────────────────────────────
# LLMClient 基础测试
# ──────────────────────────────────────────

def test_llm_client_no_api_key():
    """无 API Key 时返回 error 状态，不抛异常。"""
    client = LLMClient(api_key="", api_base="", model="qwen-plus")
    resp = client.chat([{"role": "user", "content": "test"}])
    assert resp.status == "error"
    assert "No API key" in resp.error


def test_llm_client_default_config():
    """默认配置正确。"""
    client = LLMClient()
    assert client.api_base  # 有默认值
    assert client.model     # 有默认模型


# ──────────────────────────────────────────
# LLMResponse 测试
# ──────────────────────────────────────────

def test_llm_response_success():
    resp = LLMResponse(
        content="你好，世界",
        model="qwen-plus",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    )
    assert resp.status == "success"
    assert resp.content == "你好，世界"
    assert resp.usage["total_tokens"] == 30


def test_llm_response_error():
    resp = LLMResponse(content="", model="qwen", status="error", error="timeout")
    assert resp.status == "error"
    assert resp.error == "timeout"


# ──────────────────────────────────────────
# Mock LLM Client
# ──────────────────────────────────────────

class MockLLMClient:
    """模拟 LLM 客户端，用于测试。"""
    
    def __init__(self, reply: str = "Hello from mock LLM"):
        self.reply = reply
        self.call_count = 0
        self.last_messages = []
    
    def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        self.call_count += 1
        self.last_messages = messages
        return LLMResponse(
            content=self.reply,
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )


# ──────────────────────────────────────────
# Agent + LLM 集成测试
# ──────────────────────────────────────────

def test_agent_run_without_llm_simulated():
    """无 LLM client 时，run() 返回 simulated 模式。"""
    spec = AgentSpec(name="test", role="tester", system_prompt="test", skills=["x"])
    agent = Agent(spec)
    result = agent.run("hello")
    assert result["status"] == "simulated"
    assert "[Simulated]" in result["reply"]


def test_agent_run_with_llm():
    """有 LLM client 时，run() 调用 LLM 并返回真实回复。"""
    spec = AgentSpec(name="test", role="tester", system_prompt="test", skills=["x"])
    mock_llm = MockLLMClient(reply="42 is the answer")
    agent = Agent(spec, llm_client=mock_llm)
    
    result = agent.run("What is the answer?")
    
    assert result["status"] == "success"
    assert result["reply"] == "42 is the answer"
    assert result["model"] == "mock-model"
    assert result["usage"]["total_tokens"] == 30
    assert mock_llm.call_count == 1


def test_agent_run_llm_error():
    """LLM 调用失败时，run() 返回 error 状态。"""
    spec = AgentSpec(name="test", role="tester", system_prompt="test", skills=["x"])
    
    class FailingLLM:
        def chat(self, messages):
            return LLMResponse(content="", model="fail", status="error", error="connection refused")
    
    agent = Agent(spec, llm_client=FailingLLM())
    result = agent.run("hello")
    
    assert result["status"] == "llm_error"
    assert "[LLM Error]" in result["reply"]
    assert "connection refused" in result["reply"]


def test_agent_build_messages():
    """_build_messages 正确构建 system + history + query。"""
    spec = AgentSpec(
        name="builder",
        role="builder role",
        system_prompt="You are a builder",
        skills=["x"],
    )
    agent = Agent(spec)
    
    # 第一次调用
    messages = agent._build_messages("first query")
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a builder"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "first query"
    
    # 多轮对话后
    agent.run("q1")
    messages = agent._build_messages("q2")
    # system + history (user q1 + assistant reply) + user q2 = 4 条
    # 注意：无 LLM 时 simulated 回复也计入 history
    assert len(messages) >= 3  # system + user q1 + (optional: assistant simulated) + user q2
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "q2"


def test_agent_run_with_system_prompt_from_spec():
    """system_prompt 来自 AgentSpec。"""
    spec = AgentSpec(
        name="expert",
        role="税务专家",
        system_prompt="你是一个专业的税务顾问，擅长解答税法问题。",
        recipes=["tax"],
    )
    mock_llm = MockLLMClient(reply="Tax advice here")
    agent = Agent(spec, llm_client=mock_llm)
    
    agent.run("如何报税？")
    
    # 检查 system prompt 是否正确传递
    system_msg = mock_llm.last_messages[0]
    assert system_msg["role"] == "system"
    assert "税务顾问" in system_msg["content"]


def test_agent_history_updated_after_llm():
    """LLM 调用后，history 正确更新。"""
    spec = AgentSpec(name="h", role="r", system_prompt="s", skills=["x"])
    mock_llm = MockLLMClient(reply="LLM reply")
    agent = Agent(spec, llm_client=mock_llm)
    
    agent.run("question 1")
    
    assert len(agent.history) == 2
    assert agent.history[0]["content"] == "question 1"
    assert agent.history[1]["content"] == "LLM reply"


def test_agent_run_multiple_times():
    """多轮对话，LLM 被多次调用。"""
    spec = AgentSpec(name="multi", role="r", system_prompt="s", skills=["x"])
    mock_llm = MockLLMClient(reply="OK")
    agent = Agent(spec, llm_client=mock_llm)
    
    agent.run("msg 1")
    agent.run("msg 2")
    agent.run("msg 3")
    
    assert mock_llm.call_count == 3
    assert len(agent.history) == 6  # 3 pairs


# ──────────────────────────────────────────
# Assembler + LLM 集成
# ──────────────────────────────────────────

def test_assembler_assemble_agent_with_llm(tmp_path):
    """Assembler.assemble_agent() 注入 LLM client。"""
    recipes_dir = tmp_path / "recipes"
    skills_dir = tmp_path / "skills"
    recipes_dir.mkdir()
    skills_dir.mkdir()
    
    # 创建一个测试配方
    import json
    recipe = {
        "name": "test-recipe",
        "trigger_keywords": ["test"],
        "skills": [],
    }
    (recipes_dir / "test-recipe.json").write_text(json.dumps(recipe))
    
    mock_llm = MockLLMClient(reply="assembled!")
    assembler = Assembler(str(recipes_dir), str(skills_dir), llm_client=mock_llm)
    
    spec = AgentSpec(
        name="assembled-agent",
        role="test",
        system_prompt="You are assembled",
        recipes=["test-recipe"],
    )
    
    agent = assembler.assemble_agent(spec)
    
    assert isinstance(agent, Agent)
    assert agent._llm is mock_llm  # LLM client 已注入
    
    # Agent 可以正常 run
    result = agent.run("hello")
    assert result["reply"] == "assembled!"
    assert mock_llm.call_count == 1


def test_assembler_assemble_agent_without_llm(tmp_path):
    """Assembler.assemble_agent() 不注入 LLM client 时，simulated 模式。"""
    recipes_dir = tmp_path / "recipes"
    skills_dir = tmp_path / "skills"
    recipes_dir.mkdir()
    skills_dir.mkdir()
    
    assembler = Assembler(str(recipes_dir), str(skills_dir))  # 无 LLM
    
    spec = AgentSpec(
        name="no-llm-agent",
        role="test",
        system_prompt="test",
        skills=["x"],
    )
    
    agent = assembler.assemble_agent(spec)
    result = agent.run("hello")
    
    assert result["status"] == "simulated"
