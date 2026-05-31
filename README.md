# Agent Assembler 🧩

**Deterministic Context Assembly for AI Agents.**

> *Stop praying your LLM understands your prompt. Start engineering it.*

Agent Assembler is a lightweight, "Recipe-First" middleware for AI Agents.
It solves the **"Monolith Context"** problem: loading massive, bloated system prompts
that confuse models, waste tokens, and cause hallucinations.

Instead, it uses **Just-In-Time (JIT) Assembly**:
1.  **Match**: Matches user intent to a pre-defined "Recipe" (JSON).
2.  **Load**: Fetches only the tiny, atomic "Skills" needed for that specific task.
3.  **Assemble**: Splices them into a precise, high-signal System Prompt.

## 🚀 Why Use It?

- **📉 Cut Context by 70%**: Load 4KB of relevant rules instead of 50KB of bloat.
- **🛡️ Prevent Hallucination**: "Solid Container" architecture. The model only sees tools/rules it is *allowed* to use.
- **🔧 No Code Changes Required**: Plug it into any framework (LangChain, CrewAI, OpenClaw) as a pre-processor.

## 📦 Installation

```bash
pip install agent-assembler
```

## 🛠️ Quick Start

### 1. Define a Recipe (`recipes/excel.json`)
A recipe maps keywords to specific, atomic skills.

```json
{
  "name": "excel_analysis",
  "trigger_keywords": ["Excel", "Data Analysis", "Visualization"],
  "skills": ["read-process", "clean-data", "viz-chart"]
}
```

### 2. Create Atomic Skills (`skills/read-process/SKILL.md`)
Keep your skills small (<4KB) and focused.

```markdown
# Excel Read & Process
... (Specific rules and code for reading Excel)
```

### 3. Assemble in Python

```python
from agent_assembler import Assembler

assembler = Assembler(
    recipes_dir="./recipes",
    skills_dir="./skills"
)

# User Input
query = "Analyze this Excel file for anomalies"

# JIT Assembly
result = assembler.assemble(query)

print(f"Loaded Recipe: {result['recipe']}")
print(f"Skills Loaded: {result['skills_loaded']}")
# result['system_prompt'] is now ready for your LLM!
```

## 🏗️ Architecture: Liquid vs. Solid

- **Liquid Intelligence (LLM)**: The model's probabilistic reasoning power.
- **Solid Container (Assembler)**: The rigid structure (Recipes + Skills) that shapes the intelligence.

Without a container, water floods the house. With a container, it turns the turbine.

## 📜 License

MIT
