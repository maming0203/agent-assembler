---
title: Agent Assembler Tasks
status: active
---

# Project Tasks: Agent Assembler

## ✅ Phase 1 (SDK Decoupling) — COMPLETE

- [x] **1.1 Structure Refactoring**: Move to `src/` layout.
- [x] **1.2 Core Logic Migration**: Assembler, Recipe, SkillRef classes.
- [x] **1.3 Unit Testing**: 14 tests passing (7 core + 7 adapter).
- [x] **1.4 Alpha Release**: `agent_assembler-0.2.0.dev1` wheel built & verified.

## ✅ Phase 2 (Adapters) — COMPLETE

- [x] **2.1 Adapter Interface**: `BaseAdapter` abstract class.
- [x] **2.2 Coze Adapter**: Recipe → Coze DSL, JIT skill injection, validation.
- [x] **2.3 Qianwen Adapter**: Recipe → 千问/百炼格式, 中文 Prompt 优化.
- [x] **2.4 Gateway Integration**: `/api/v1/export` endpoint on ECS.

## 🚧 Phase 3 (SaaS) — IN PROGRESS

- [x] **3.1 Web Dashboard**: Streamlit frontend with tenant isolation.
- [ ] **3.2 Mini Program Integration**: Connect `miniprogram-recipes` to ECS Gateway.
- [ ] **3.3 Core Loop Verification**: `/api/v1/run` end-to-end (waiting for OpenClaw activation).

## ⬜ Phase 4 (Distribution) — PLANNED

- [ ] **4.1 Recipe Library**: Curate 5-10 high-quality seed scenarios.
- [ ] **4.2 Auto-Craft Polish**: Improve recipe generation success rate.
- [ ] **4.3 Coze Deployment**: One-click publish from Dashboard to Coze API channel.
- [ ] **4.4 PyPI Release**: Publish `agent-assembler` package.
