# Agent Assembler Changelog

## 2026-06-08 — v0.3.0: SDK Hardening + Recipe Registry

### P4 — SDK Hardening
- **Agent class + AgentSpec**: Dataclass-driven Agent blueprint (name, role, system_prompt, recipes, skills, sidecars, platform, model, config)
- **assemble_agent()**: Spec → Agent factory method on Assembler
- **Sidecar Bus skeleton**: SidecarBase, SidecarBus, DecisionEngine, Simulator, Analytics
- **Version**: `__version__ = "0.3.0"` in `__init__.py`
- **Exports**: 12 public classes (Agent, AgentSpec, Assembler, Recipe, RecipeRegistry, RecipeVersion, SidecarBase, SidecarBus, DecisionEngine, Simulator, Analytics)
- **Tests**: 40/40 passing (16 new + 24 existing)

### P4.3 — Recipe Registry
- **RecipeRegistry**: Search by keyword/tag, tag-based filtering, import/export, version management
- **RecipeVersion**: Semantic version tracking for recipes
- **Git**: 7f9ee06

### P2 — Bug Fixes (5 bugs)
- Schema: Added `script_path` field to recipe_schema.json
- Paths: Hard-coded paths in config.py → env-var first
- Resource leaks: 5x `json.load(open())` → `with open()` (db.py 3处 + core.py 2处)
- AutoCraft: `_generate_skill_py()` auto-generates .py skill files with recipes
- Tests: +10 gateway tests + `/api/v1/health` endpoint, 24/24 pytest green

### P1 — Architecture Refactoring
- `api_gateway.py` (1188行) → `api_gateway/` package (6 modules, all <300 lines)
- Modules: config.py, core.py, multimodal.py, autocraft.py, script_engine.py, db.py
- 14/14 pytest passing

### P0 — Core Stabilization
- Synced latest gateway + autocraft + multimodal support
- Git: d195c21

---

## 2026-06-03 - MVP 全链路闭环与体验升级

### 🚀 核心里程碑
- **端到端 (E2E) 跑通**: 小程序 -> HTTPS Gateway -> 配方路由 -> Skill 加载 -> Agent 执行。
- **云端环境就绪**: 配方库 (200+) + Skills (6 大类) 同步完成，13 个 Agent 在线。
- **GitHub 占坑**: 核心引擎代码 (`api_gateway.py`) 与 README 已推送至 `maming0203/agent-assembler`。

### 🛠️ 关键修复
- **路径自适应**: 解决云端 (Linux) 与本地 (Mac) 路径不一致导致的 Skill 加载失败 (`IS_CLOUD` 逻辑)。
- **执行权限**: 修复 `call_agent` 中 `su - admin` 在云端 root 下卡死的问题。
- **优先级逻辑**: 重构 `find_recipe`，确保普通配方优先于 Premium 配方匹配。

### 🎨 体验优化
- **拒绝干等**: 增加动态进度提示（匹配中 → 加载技能 → 思考中）。
- **排版增强**: 支持 Markdown **表格**、代码块解析，UI 升级为 iOS 风格气泡与卡片。
- **引导页**: 增加 Welcome 界面与 4 个热门场景快捷入口。

### 🛡️ 身份脱敏
- **云端去重**: 移除 Agent 身份中的“星光卫视/全域文旅”前缀，变为通用专业身份。
- **指令拦截**: 注入 System Prompt 拦截内部文件路径（如 `~/星光卫视Wiki`），强制纯文本输出。
