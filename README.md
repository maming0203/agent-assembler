# Agent Assembler 🧩

> **The On-Demand Digital Arsenal for the AI Era.**
> Deterministic Context Assembly for Multi-Agent Distribution Network.

<p align="center">
  <img src="https://img.shields.io/badge/version-v0.5.0-blue.svg" alt="version">
  <a href="https://pypi.org/project/agent-assembler"><img src="https://img.shields.io/pypi/v/agent-assembler" alt="PyPI"></a>
</p>

> **We don't build the Aircraft Carriers (LLMs); we build the 4S Shop.**
> Agent Assembler is the **core engine** that powers multi-agent systems, turning non-standard business requirements into standardized, executable AI Agents.

---

## 🚀 Why Agent Assembler?

In the current AI landscape, Large Language Models provide immense "intelligence," yet they often fail in critical business scenarios due to a lack of **Domain Knowledge** and **Deterministic Logic**.

| Feature | Traditional SaaS | Traditional Outsourcing | **Agent Assembler** |
| :--- | :--- | :--- | :--- |
| **Delivery** | Rigid, standard accounts | Expensive, slow human labor | **On-demand digital production** |
| **Flexibility** | Low (Roadmap dependent) | High (Cost scales linearly) | **Extreme (Sidecar hot-plugging)** |
| **Core Asset** | Vendor's platform code | Client's private code | **The Recipe Matrix (Industry Wisdom)** |
| **Marginal Cost** | Low (per seat) | High (per project) | **Near Zero (per assembly)** |

Agent Assembler bridges the gap with a **"Recipe + Sidecar"** architecture, allowing domain experts to convert tacit industry knowledge into executable digital assets.

---

## 🏗️ Core Architecture

### 1. Micro-kernel + Sidecar Bus

The core soul of the framework — decoupling core logic from auxiliary capabilities for maximum flexibility.

- **🥘 Pot (The Recipe)**: Encapsulates essential business logic and data flow (e.g., Profit Calculation, Compliance Check).
- **🔌 Sidecar Bus (Pluggable Plugins)**: Capabilities are hot-swappable via a standard bus:
  - **🧠 Decision Engine**: Deterministic analysis & "Red-Yellow-Green" verdicts.
  - **🎭 Simulator**: Immersive role-play for business negotiation training.
  - **📊 Analytics**: Data persistence and visualization pipelines.
- **🏭 Factory (The Assembler)**: Orchestrates the "Pots" and "Lids" to assemble and deploy specific Agents.

### 2. JIT Assembly & Atomic Design

- **Recipe-First**: Intent matching against pre-defined JSON recipes.
- **Atomic Skills (<4KB)**: Focused, composable modules that do one thing well.
- **AutoCraft**: Automated generation engine transforming unstructured requirements into deployed scripts with zero-marginal-cost.

### 3. Multi-Platform Adapters

Deploy assembled Agents to any platform with one click: **Qianwen, Coze, WeChat**, and more.

---

## 🛠️ Installation & Quick Start

```bash
pip install agent-assembler
```

```python
from agent_assembler import Assembler, Agent, AgentSpec, SidecarBus

# Quick JIT assembly
assembler = Assembler(recipes_dir="./recipes", skills_dir="./skills")
result = assembler.assemble("Analyze this excel file")
print(result['system_prompt'])

# Spec-driven Agent assembly
spec = AgentSpec(name="Tax Advisor", role="财务顾问", recipes=["tax_consulting"])
agent = assembler.assemble_agent(spec)

# Sidecar Bus (pluggable capabilities)
bus = SidecarBus(decision_engine=True, simulator=True, analytics=True)
```

---

## 🎯 From Sandbox to Matrix

Our architecture is **Domain-Agnostic**. It works anywhere.

1. **🧪 The Sandbox (Validation Phase)**
   - Validated in high-noise, non-standard environments (e.g., Tier-3/4 city retail & dining markets).
   - **Proven**: Solves "messy accounts," compliance risks, and performance disputes with "Micro-Deductions" (calculating exact break-even points in seconds).

2. **🌍 The Matrix (Expansion Phase)**
   - **Zero Code Change** required at the core engine level.
   - **Cross-Border E-commerce**: Inventory turnover optimization.
   - **Manufacturing**: Production line yield simulation.
   - **Compliance**: Automated contract auditing.

---

## 🗺️ Roadmap

| Phase | Goal | Status |
| :--- | :--- | :--- |
| **P0** | Core Stabilization & Validation | ✅ Done |
| **P1** | Architecture Refactoring (api_gateway → modular) | ✅ Done |
| **P2** | Bug Fixes (schema, paths, resource leaks, test coverage) | ✅ Done |
| **P3** | Documentation Alignment | ✅ Done |
| **P4** | SDK Hardening (Agent/AgentSpec/Sidecar Bus) | ✅ Done |
| **P4.3** | Recipe Registry (search, tags, version management) | ✅ Done |
| **P4.4** | LLM Full Chain (LLMClient, Agent.run) | ✅ Done |
| **Sidecar** | Decision Engine, Simulator, Analytics | ✅ Done |
| **P5** | SaaS Dashboard & No-Code Builder | ✅ Done |
| **AutoCraft v2** | Schema fix, .md skills, validation | ✅ Done |

---

## 🔮 Vision

We are building the **Salesforce of the AI Era**.

We provide not just tools, but an infrastructure for global developers and industry experts to co-build a **Commercial Wisdom Recipe Library**.

> *"The future is already here — it's just not evenly distributed. We are the pipeline builders."*

---

## 📜 License

Apache 2.0 (Core SDK) / Commercial (Proprietary Recipes)
