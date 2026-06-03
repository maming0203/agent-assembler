# Agent Assembler 🧩

> **Deterministic Context Assembly for AI Agents.**
> The Engine for the Multi-Agent Distribution Network.

## 1. Vision
**From JIT Engine to Agent Factory & Distribution Network.**
Agent Assembler is no longer just a script; it is the **core engine** that powers multi-agent systems across platforms (Qianwen, Coze, WeChat, etc.).

## 2. Core Architecture
- **Recipe-First**: Intent matching pre-defined JSON recipes.
- **Atomic Skills**: <4KB focused skill modules.
- **JIT Assembly**: Assemble only what is needed, when it is needed.
- **Multi-Platform Adapters**: Deploy to Qianwen, Coze, Baidu, and more with one click.

## 3. Roadmap
| Phase | Goal | Status |
|-------|------|--------|
| **P0** | Core Stabilization & Validation | ✅ Done |
| **P1** | **SDK Decoupling & Standardization** | 🚧 Active |
| **P2** | Multi-Platform Adapters (Coze/Qianwen) | ⬜ Planned |
| **P3** | SaaS Dashboard & No-Code Builder | ⬜ Planned |

## 4. Installation
```bash
pip install agent-assembler
```

## 5. Quick Start
```python
from agent_assembler import Assembler

assembler = Assembler(recipes_dir="./recipes", skills_dir="./skills")
result = assembler.assemble("Analyze this excel file")
print(result['system_prompt'])
```
