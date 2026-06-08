"""测试 Sidecar 总线与插件。"""

import pytest
from agent_assembler.sidecar.base import SidecarBase, SidecarBus
from agent_assembler.sidecar.decision import DecisionEngine, Rule
from agent_assembler.sidecar.simulator import Simulator, BUILTIN_SCENES
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
    sim = Simulator()
    bus.register(sim)
    result = bus.pre_process_all("hello")
    # Simulator 在没有激活场景时不做修改
    assert result == "hello"


def test_sidecar_bus_post_process_all():
    bus = SidecarBus()
    engine = DecisionEngine()
    bus.register(engine)
    result = bus.post_process_all({"agent": "x", "reply": "test reply content"})
    # DecisionEngine 对非空 reply 做判定
    assert "decision" in result


# --- DecisionEngine ---

def test_decision_engine_basic():
    engine = DecisionEngine()
    assert engine.pre_process("test") == "test"
    out = engine.post_process({"agent": "x", "reply": "a good response"})
    assert out["decision"]["verdict"] == "green"


def test_decision_engine_red_trigger():
    engine = DecisionEngine()
    out = engine.post_process({"agent": "x", "reply": "error: something failed"})
    assert out["decision"]["verdict"] == "red"


def test_decision_engine_yellow_short():
    engine = DecisionEngine()
    out = engine.post_process({"agent": "x", "reply": "short"})
    # "short" 长度 <10 但 >=5 → yellow (too_short 触发，但不到 red 级别)
    assert out["decision"]["verdict"] == "yellow"


def test_decision_engine_custom_rule():
    engine = DecisionEngine()
    engine.add_rule(Rule("no_email", r"\b\w+@\w+\.\w+\b", "regex", "red", "禁止输出邮箱"))
    out = engine.post_process({"agent": "x", "reply": "联系 test@example.com"})
    assert out["decision"]["verdict"] == "red"
    assert "no_email" in out["decision"]["triggered_rules"]


def test_decision_engine_list_rules():
    engine = DecisionEngine()
    rules = engine.list_rules()
    assert len(rules) >= 3  # 至少 3 个预置规则


def test_decision_engine_remove_rule():
    engine = DecisionEngine()
    assert engine.remove_rule("too_short") is True
    assert engine.remove_rule("nonexistent") is False


# --- Simulator ---

def test_simulator_list_scenes():
    sim = Simulator()
    scenes = sim.list_scenes()
    assert len(scenes) >= len(BUILTIN_SCENES)


def test_simulator_load_scene():
    sim = Simulator()
    assert sim.load_scene("price-negotiation") is True
    assert sim.active_scene is not None
    assert sim.active_scene.name == "价格谈判"


def test_simulator_load_nonexistent():
    sim = Simulator()
    assert sim.load_scene("nonexistent-scene") is False


def test_simulator_active_scene_prompt():
    sim = Simulator()
    sim.load_scene("price-negotiation")
    prompt = sim.active_scene.to_prompt()
    assert "价格谈判" in prompt
    assert "供应商销售代表" in prompt


def test_simulator_with_scene_pre_process():
    sim = Simulator()
    sim.load_scene("price-negotiation")
    result = sim.pre_process("你好")
    assert "模拟场景" in result
    assert "价格谈判" in result


def test_simulator_post_process_tracks_turns():
    sim = Simulator()
    sim.load_scene("price-negotiation")
    sim.pre_process("你好")
    out = sim.post_process({"reply": "你好，欢迎"})
    assert out["simulator"]["scene"] == "价格谈判"
    assert out["simulator"]["turn"] == 1


def test_simulator_session_log():
    sim = Simulator()
    sim.load_scene("price-negotiation")
    sim.pre_process("你好")
    sim.post_process({"reply": "你好"})
    assert len(sim.session_log) == 2


def test_simulator_evaluate_session():
    sim = Simulator()
    sim.load_scene("price-negotiation")
    result = sim.evaluate_session()
    assert "scene" in result
    assert result["scene"] == "价格谈判"


# --- Analytics ---

def test_analytics_basic():
    a = Analytics()
    assert a.pre_process("test") == "test"
    out = a.post_process({"query": "q1", "agent": "a1", "reply": "hello"})
    assert out["analytics_tracked"] is True
    assert a.count == 1


def test_analytics_latest():
    a = Analytics()
    a.post_process({"query": "q1", "agent": "a1", "reply": "r1"})
    a.post_process({"query": "q2", "agent": "a1", "reply": "r2"})
    latest = a.latest(2)
    assert len(latest) == 2
    # 内存存储按 append 顺序，最新在最后
    assert latest[-1]["query"] == "q2"


def test_analytics_summary():
    a = Analytics()
    a.post_process({"query": "q1", "agent": "a1", "reply": "r1"})
    a.post_process({"query": "q2", "agent": "a2", "reply": "r2"})
    s = a.summary()
    assert s["count"] == 2
    assert "a1" in s["agent_breakdown"]
    assert "a2" in s["agent_breakdown"]


def test_analytics_top_queries():
    a = Analytics()
    a.post_process({"query": "same", "agent": "a1", "reply": "r"})
    a.post_process({"query": "same", "agent": "a1", "reply": "r"})
    a.post_process({"query": "other", "agent": "a1", "reply": "r"})
    top = a.top_queries()
    assert top[0]["query"] == "same"
    assert top[0]["cnt"] == 2


def test_analytics_export_json(tmp_path):
    a = Analytics()
    a.post_process({"query": "q1", "agent": "a1", "reply": "r1"})
    path = tmp_path / "metrics.json"
    a.export_json(str(path))
    assert path.exists()
    assert path.stat().st_size > 0


def test_analytics_export_csv(tmp_path):
    a = Analytics()
    a.post_process({"query": "q1", "agent": "a1", "reply": "r1"})
    path = tmp_path / "metrics.csv"
    a.export_csv(str(path))
    assert path.exists()


def test_analytics_sqlite_persistence(tmp_path):
    db = tmp_path / "analytics.db"
    a = Analytics(db_path=str(db))
    a.post_process({"query": "q1", "agent": "a1", "reply": "r1"})
    a.post_process({"query": "q2", "agent": "a2", "reply": "r2"})
    
    # 新建实例读同一数据库
    a2 = Analytics(db_path=str(db))
    assert a2.count == 2
    s = a2.summary()
    assert s["count"] == 2
    a.close()
    a2.close()
