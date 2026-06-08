# Agent Assembler Changelog

## 2026-06-08 — v0.5.0: SaaS Dashboard + Gateway API 补齐 + Sidecar 引擎

### P5 — Gateway API 补齐 (13 新端点)
- **Recipe CRUD**: `GET/POST/PUT/DELETE /api/v1/recipes` — 完整配方管理
- **Recipe 搜索**: `GET /api/v1/recipes/search?q=xxx`
- **API Key 管理**: `POST/GET/DELETE /api/v1/apikeys` — `sk-xxx` 格式密钥生成与吊销
- **Metrics**: `GET /api/v1/metrics` + `/metrics/summary` — 运行指标与汇总统计
- **Deploy**: `POST /api/v1/deploy/coze` + `/deploy/qianwen` — 一键发布准备
- **文件**: 新增 `api_gateway/p5_routes.py`
- **测试**: +13 新测试, 105/105 全绿

### P5.3+P5.4 — Dashboard 增强
- 新增 `/api/v1/metrics/timeseries` 时序指标端点
- 新增 `/api/v1/deploy/coze/complete` 完整 Coze 发布流程
- Dashboard Analytics 页: 增加近 7 天趋势图 + Top 用户表格

### Sidecar 旁挂引擎做实
- **DecisionEngine**: 规则引擎 (regex/keyword/length) + LLM 语义判定 + 红黄绿 verdict
- **Simulator**: 3 个预置场景 (价格谈判/合同审核/客户投诉) + 会话管理 + 提示系统
- **Analytics**: SQLite 持久化 + 统计汇总 + Top 查询 + JSON/CSV 导出
- **测试**: +19 新 Sidecar 测试

### AutoCraft v2 — 4 个问题修复
- Schema 路径断裂 → 使用 `config.py` 中 `RECIPE_SCHEMA_PATH`
- 技能文件格式 → 统一为 `.md`（原 `.py`），含角色定义/工作流程/输出格式/约束
- 校验强化 → `trigger_keywords` 至少 2 个 / `name` 必填 / skills 只接受字符串
- 自动修复 → 缺失 name/keywords 时自动补全并重试
- **测试**: 110/110 全绿 (+5 autocraft 修复测试)

### 其他变更
- 修复 PyPI badge 为自动获取最新版本
- Adapter 逻辑保持从 SDK import，无重复代码
- 清理: 移除过时文件，重组 uploads/dist/autocraft 目录

---

## 2026-06-07 — v0.4.0: LLM 全链路 + Recipe Registry

### P4.4 — LLM Full Chain
- **llm.py**: `LLMClient` (OpenAI-compatible, DashScope 默认) + `LLMResponse`
- **Agent.run()**: 真实 LLM 调用 + 模拟 fallback + 错误处理
- **Agent._build_messages()**: system prompt + history + query 构建
- **Assembler**: `llm_client` 参数, `assemble_agent()` 配方/skill 加载注入
- **测试**: 61 → 74 (全部通过, +13 新测试)

### P4.3 — Recipe Registry
- **RecipeRegistry**: 关键词/标签搜索, 标签过滤, 导入/导出, 版本管理
- **RecipeVersion**: 语义化版本追踪
- **测试**: +24 新 registry 测试

### P4 — Agent & Sidecar 骨架
- **AgentSpec**: Dataclass with validation (name, system_prompt, recipes/skills required)
- **Agent**: 运行时类, 支持 sidecar 热插拔和历史记录追踪
- **Sidecar Bus**: `SidecarBase`, `SidecarBus` with register/unregister/pre_process_all/post_process_all
- **3 个 sidecar 组件**: DecisionEngine, Simulator, Analytics
- **assemble_agent()**: Assembler 上的配方 → Agent 工厂方法
- **版本**: `__version__ = "0.4.0"`
- **测试**: 40/40 通过 (+16 新测试)

---

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
- **云端去重**: 移除 Agent 身份中的"星光卫视/全域文旅"前缀，变为通用专业身份。
- **指令拦截**: 注入 System Prompt 拦截内部文件路径（如 `~/星光卫视Wiki`），强制纯文本输出。
