"""测试 Sidecar 总线与插件。"""

import pytest
from agent_assembler.sidecar.base import SidecarBase, SidecarBus
from agent_assembler.sidecar.decision import DecisionEngine
from agent_assembler.sidecar.simulator import Simulator
from agent_assembler.sidecar.analytics import Analytics


# --- SidecarBus 管理 ---

def test_sidecar_bus_register():
    bus = SidecarBus()
    engine = DecisionEngine()
    bus.register(engine)
    assert bus.get("decision") is engine


def test_sidecar_bus_unregister():
    bus = SidecarBus()
    bus.register(DecisionEngine())
    bus.unregister("decision")
    assert bus.get("decision") is None


def test_sidecar_bus_list():
    bus = SidecarBus()
    bus.register(DecisionEngine())
    bus.register(Simulator())
    meta_list = bus.list_sidecars()
    assert len(meta_list) == 2
    names = [m["name"] for m in meta_list]
    assert "decision" in names
    assert "simulator" in names


def test_sidecar_bus_pre_process_all():
    bus = SidecarBus()
    bus.register(Simulator())
    result = bus.pre_process_all("hello")
    assert result == "[模拟模式] hello"


def test_sidecar_bus_post_process_all():
    bus = SidecarBus()
    bus.register(DecisionEngine())
    result = bus.post_process_all({"agent": "x"})
    assert result["decision"] == "green"
    assert "decision_note" in result


# --- DecisionEngine ---

def test_decision_engine_basic():
    engine = DecisionEngine()
    assert engine.pre_process("test") == "test"
    out = engine.post_process({"data": 1})
    assert out["decision"] == "green"


# --- Simulator ---

def test_simulator_basic():
    sim = Simulator()
    assert "[模拟模式]" in sim.pre_process("hello")
    out = sim.post_process({})
    assert out["simulator_mode"] is True


# --- Analytics ---

def test_analytics_basic():
    a = Analytics()
    assert a.pre_process("test") == "test"
    out = a.post_process({"query": "q1", "agent": "a1"})
    assert out["analytics_tracked"] is True
    assert len(a.metrics) == 1
    assert a.metrics[0]["query"] == "q1"
