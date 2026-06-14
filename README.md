# Agent Assembler

**AI Agent 配方工厂 — 从自然语言到可执行配方的自动化生产线**

> v1.1.0 | 2026-06-14


## 🏗️ JIT 分层架构

Agent Assembler 实现了 **JIT (Just-In-Time Context Assembly)** 模式——按需组装上下文，而非全量加载。

### 两层模型

```
JIT 组装 = 基础设施层（无条件注入） + 任务层（按需组装）
```

| 层级 | 加载方式 | 例子 |
|------|----------|------|
| **基础设施层** | 无条件注入，所有配方输出都遵守 | 输出格式规范、安全约束 |
| **任务层** | 根据用户 query 匹配配方，按需加载 | 保本点计算、违禁词检测 |

### 为什么需要两层？

- **全量加载**：不会漏，但 token 爆炸、噪音淹没信号
- **纯 JIT**：精准省 token，但依赖组装者的认知上限——容易漏掉"基础设施"

**基础设施层**解决 JIT 的盲区：有些约束跟任务内容无关，所有输出都要遵守（如 Markdown 必须有 YAML 头）。这些不该出现在 JIT 判断流程里，应该无条件注入。

### 配置

```python
# api_gateway/config.py
INFRASTRUCTURE_SKILLS = [
    "obsidian-doc-format",  # 所有 Markdown 输出必须有 YAML Frontmatter
]
```

新增基础设施 Skill：编辑此清单，所有配方自动继承。

---

## 核心能力

### 🏭 AutoCraft v4 — 自动化配方生成

```
自然语言 → LLM 生成 → 产物生成(Jinja2) → 结构化验证 → 独立评估 → 质量门禁 → 入库
```

- **4 产物自动生成**: Recipe JSON + Python 脚本 + SKILL.md + MCP 配置
- **P0 独立评估器**: 独立上下文验证，防止"自卖自夸"
- **P2b 质量门禁**: 6 维评分（命名/关键词/执行时间/文件大小/字段完整性/版本号），< 70 分拒绝发布
- **自动重试**: 任一关卡失败自动清理产物并重试（最多 3 次）

### 🔄 工作流引擎

- **DAG 拓扑排序** (Kahn 算法)
- **条件分支** (8 种操作符 + 风险等级感知)
- **跨 step 一致性校验** (P2a)
- **异常处理策略** (abort/skip/retry/fallback)
- **并行组支持**

### 🌐 多平台适配

一个配方，四种输出：

| 平台 | 格式 |
|------|------|
| 微信 | rich_text (sections + table) |
| 钉钉 | actionCard (markdown + btns) |
| 飞书 | interactive (card.elements) |
| 企微 | template_card (text_notice) |

### 🛡️ 质量保障体系

```
生成 → 评估 → 拦截 → 门禁 → 分发
  ↓       ↓       ↓       ↓       ↓
AutoCraft Evaluator Consistency Quality  Adapter
         (P0)     (P2a)     Gate    (P2d)
                            (P2b)
```

每一层独立校验，脏数据和低质量配方到不了用户面前。

## 硬配方库

### P0 级（带脚本 + 测试）

| 配方 | 能力 |
|------|------|
| 门店糊涂账计算器 | 保本点、日/月营业额、利润 |
| 员工提成计算器 | 底薪+提成+社保 |
| 广告违禁词检测 | 广告法违禁词扫描 |
| 沧州商户工具包 | 3 合 1（利润+工资+违禁词） |

### P1 级

| 配方 | 能力 |
|------|------|
| 销售提成模拟器 | 固定/阶梯/毛利/混合四种模式 |
| 战略决策引擎 | SWOT+PEST+波特五力 |
| 营销 ROI 优化器 | 渠道 ROI 计算+预算分配 |

## 架构

```
Agent Assembler
├── autocraft_v4.py      # AutoCraft v4 主引擎
├── template_engine.py   # Jinja2 模板引擎
├── recipe_validator.py  # 配方结构化验证器
├── workflow_engine.py   # DAG 工作流引擎
├── trinity_routes.py    # Trinity 执行路由
├── db.py                # 配方匹配 + 计费
├── platforms/           # 多平台适配器
│   ├── dingtalk/
│   ├── feishu/
│   └── wecom/
└── templates/           # Jinja2 模板
    ├── recipe_json.j2
    ├── recipe_script.j2
    ├── skill_md.j2
    └── mcp_config.j2
```

## 快速开始

### 启动 Gateway

```bash
cd agent-assembler
uvicorn api_gateway.core:app --host 0.0.0.0 --port 8000
```

### 触发 AutoCraft

```bash
curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -H "x-api-key: ***" \
  -d '{"query": "帮我设计一个宠物店会员积分兑换系统"}'
```

### 多平台分发

```bash
curl -X POST http://localhost:5000/api/v1/execute \
  -H "Content-Type: application/json" \
  -H "x-api-key: ***" \
  -d '{
    "skill": "cangzhou_merchant_pack",
    "query": "房租8000，3个员工",
    "platform": "dingtalk"
  }'
```

## 技术栈

- **后端**: Python 3.11 + FastAPI + Uvicorn
- **模板**: Jinja2
- **LLM**: DashScope (Qwen)
- **部署**: systemd (ECS) / CloudBase (腾讯云)

## License

MIT
