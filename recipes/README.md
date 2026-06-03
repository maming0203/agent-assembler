# Agent Assembler Recipes

Recipe 定义了 AI Agent 的行为规范。每个 Recipe 是一个 JSON 文件，格式如下：

## JSON Schema

```json
{
    "name": "Agent 名称",
    "trigger_keywords": ["关键词1", "关键词2"],
    "skills": ["skill-name-1", "skill-name-2"],
    "notes": "Agent 的背景描述和使用说明",
    "routing": "openclaw-agent-id"  // 可选，指定由哪个 OpenClaw Agent 执行
}
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | Agent 唯一名称 |
| trigger_keywords | string[] | ✅ | 触发关键词，用户输入匹配任一即命中 |
| skills | string[] | ❌ | 关联的 Skill 名称（对应 skills 目录下的文件夹） |
| notes | string | ❌ | Agent 描述/背景信息 |
| routing | string | ❌ | OpenClaw Agent ID（如 "legal-agent"） |

## 示例

- `contract_review.json` — 法律合同审查 Agent
- `sales_simulation.json` — 角色扮演/销售演练 Agent（含 Character Engine 配置）
- `data_analysis.json` — 数据分析 Agent

## 使用方法

```python
from agent_assembler import Assembler

assembler = Assembler(
    recipes_dir="./recipes",
    skills_dir="/path/to/skills"
)
result = assembler.assemble("帮我审一下这份合同")
```
