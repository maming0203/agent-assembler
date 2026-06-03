---
title: Agent Assembler Tasks
status: active
---

# Project Tasks: Agent Assembler

## 🚧 Active: Phase 1 (SDK Decoupling)

- [ ] **1.1 Structure Refactoring**: Move to `src/` layout. (✅ Done)
- [ ] **1.2 Core Logic Migration**: Extract `Assembler` and `Recipe` classes.
- [ ] **1.3 Unit Testing**: Add `pytest` coverage for assembly logic.
- [ ] **1.4 Alpha Release**: Build and verify `wheel` package.

## ⬜ Phase 2 (Adapters)

- [ ] **2.1 Adapter Interface**: Define `BaseAdapter` class.
- [ ] **2.2 Coze Adapter**: Map Recipe to Coze DSL.
- [ ] **2.3 Qianwen Adapter**: Map Recipe to Qianwen Agent Spec.
- [ ] **2.4 Gateway Integration**: Update `api_gateway.py` to use SDK.

## ⬜ Phase 3 (SaaS)

- [ ] **3.1 Web Dashboard**: Setup Streamlit/React frontend.
- [ ] **3.2 Multi-Tenant**: Add `tenant_id` isolation in DB.
