# AutoCraft v3 质量升级方案

## 问题诊断 (v2 → v3)

| 问题 | v2 现状 | v3 修复 |
|------|---------|---------|
| 只生成 JSON 壳子 | 生成 `trigger_keywords + routing`，无 `.py` 脚本 | LLM Prompt 强制生成配套 Python 脚本 |
| f-string 硬编码 SKILL.md | 无 YAML frontmatter、无行为规则、无 GEO 优化 | Jinja2 模板引擎生成完整 SKILL.md |
| 无自动测试 | 跑不跑得通不知道 | 生成后自动运行 `--test` 压力测试，跑通才入库 |
| 1141 配方中 87% 纯 Prompt | 只有 1.6% 有脚本 | 每个 AutoCraft 配方默认带 `.py` 脚本 |

## 升级架构

```
用户痛点 → find_recipe() 无匹配
  ↓
_dashscope_chat() 调 DashScope (v3 Prompt)
  ↓ LLM 返回: JSON + Python 脚本 + Few-shot
  ↓
_extract_json_from_response() 三级提取
_extract_python_from_response() 提取脚本
_extract_fewshot_from_response() 提取示例
  ↓
_generate_artifacts() — Jinja2 模板渲染 4 个文件:
  ├── recipe JSON (含 script_path + metadata)
  ├── Python 脚本 (validate_inputs + run_simulation + run_stress_test + --json CLI)
  ├── SKILL.md (YAML frontmatter + Few-shot + GEO 优化)
  └── mcp.json (MCP 工具声明)
  ↓
_run_validation() — 28 项检查:
  ├── Phase 1: JSON 字段校验 (7 项)
  ├── Phase 2: 文件存在性检查 (3 项)
  ├── Phase 3: 脚本内容验证 (6 项)
  ├── Phase 4: 脚本执行测试 (2 项)
  ├── Phase 5: SKILL.md 内容验证 (5 项)
  └── Phase 6: mcp.json 结构验证 (5 项)
  ↓
test_passed=true → 入库
test_passed=false → 清理文件 + 重试
```

## 文件清单

### 新增文件

| 文件 | 用途 |
|------|------|
| `api_gateway/templates/skill_md.j2` | SKILL.md Jinja2 模板（YAML frontmatter + GEO + Few-shot） |
| `api_gateway/templates/recipe_script.j2` | Python 脚本 Jinja2 模板（三件套 + --json CLI） |
| `api_gateway/templates/mcp_config.j2` | mcp.json Jinja2 模板（工具声明 + input/output schema） |
| `api_gateway/templates/recipe_json.j2` | 配方 JSON Jinja2 模板（含所有 metadata 字段） |
| `api_gateway/template_engine.py` | 模板引擎封装（4 个 render_* 函数） |
| `api_gateway/recipe_validator.py` | 验证器（28 项检查，6 个 Phase） |
| `api_gateway/autocraft_v3.py` | v3 升级版主文件 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `api_gateway/autocraft.py` | 原有 v2 保留不动，v3 作为独立模块并行 |
| `api_gateway/core.py` | 将 `auto_craft_and_run` 导入从 `autocraft` 切换到 `autocraft_v3` |

## 验证结果

- **模板渲染**: 4/4 个 Jinja2 模板渲染成功
- **RecipeValidator**: 28/28 项检查通过
- **端到端流程**: 完整生成 JSON + .py + SKILL.md + mcp.json + 测试通过
- **script_path 回填**: 自动生成并写入 recipe JSON
- **test_passed 标记**: 测试通过后自动设为 true

## 部署步骤

1. 将 `templates/`, `template_engine.py`, `recipe_validator.py`, `autocraft_v3.py` 上传到 ECS
2. 修改 `api_gateway/core.py` 的导入：
   ```python
   # 从
   from .autocraft import auto_craft_and_run, sanitize
   # 改为
   from .autocraft_v3 import auto_craft_and_run, sanitize
   ```
3. 重启 Gateway 服务
4. 用新痛点测试端到端流程
