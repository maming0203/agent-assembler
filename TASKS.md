---
title: Agent Assembler Tasks
status: active
updated: 2026-06-08
---

# Project Tasks: Agent Assembler

## ✅ P0 — Core Stabilization — COMPLETE

- [x] Sync latest gateway + autocraft + multimodal support
- [x] E2E pipeline: Mini Program → HTTPS Gateway → Recipe Routing → Skill Load → Agent Execute

## ✅ P1 — Architecture Refactoring — COMPLETE

- [x] `api_gateway.py` (1188 lines) → `api_gateway/` package (6 modules, all <300 lines)
- [x] Modules: config.py, core.py, multimodal.py, autocraft.py, script_engine.py, db.py
- [x] 14/14 pytest passing

## ✅ P2 — Bug Fixes — COMPLETE

- [x] Schema: `script_path` field added to recipe_schema.json
- [x] Paths: Hard-coded paths → env-var first (config.py)
- [x] Resource leaks: `json.load(open())` → `with open()` (5 locations)
- [x] AutoCraft: `_generate_skill_py()` generates .py skill files alongside recipes
- [x] Tests: +10 gateway tests + `/api/v1/health`, 24/24 green

## ✅ P3 — Documentation Alignment — IN PROGRESS

- [x] README.md: version v0.3.0, roadmap updated, code examples expanded
- [x] CHANGELOG.md: full P0→P4.3 history
- [x] TASKS.md: actual status aligned
- [x] `__init__.py`: `__version__ = "0.3.0"` added
- [ ] Wiki docs aligned with code (产品开发手册, etc.)
- [ ] docs/SPEC.md updated

## ✅ P4 — SDK Hardening — COMPLETE

- [x] Agent class + AgentSpec dataclass (agent.py, 159 lines)
- [x] `assemble_agent(spec: AgentSpec) → Agent` on Assembler
- [x] Sidecar Bus: SidecarBase, SidecarBus, DecisionEngine, Simulator, Analytics
- [x] `__init__.py` exports: 12 public classes
- [x] 40/40 pytest passing (16 new + 24 existing)

## ✅ P4.3 — Recipe Registry — COMPLETE

- [x] RecipeRegistry: search by keyword/tag, tag filtering, import/export
- [x] RecipeVersion: semantic version tracking
- [x] registry.py (271 lines)
- [x] recipe_template.py (221 lines)

## ⬜ P5 — SaaS Dashboard & No-Code Builder — PLANNED

- [ ] Web Dashboard with tenant isolation
- [ ] Mini Program integration with ECS Gateway
- [ ] No-code recipe builder UI
- [ ] One-click publish to Coze/Qianwen
