---
title: Agent Assembler 项目说明书 (Project Spec)
version: 1.0.0
status: Active
date: 2026-06-03
---

# Agent Assembler 项目说明书

## 1. 项目愿景 (Vision)
构建 **"Agent 时代的流水线"** —— 从 JIT 上下文引擎进化为 **多平台 Agent 工厂与分发网络**。
**核心目标**: 让业务意图一键转化为全网 (千问/抖音/微信) 可运行的 Agent。

## 2. 核心定位
- **不是**: 一个普通的 Python 脚本库，或 OpenClaw 的插件。
- **而是**: 独立的 **Agent SDK** + **适配器层 (Adapters)** + **SaaS 交付平台**。

## 3. 架构蓝图
1. **Core (核心引擎)**: 基于 `Recipe` + `Skill (<4KB)` 的 JIT 组装逻辑。
2. **SDK (开发者工具)**: 标准 Python 库 (`pip install agent-assembler`)，支持本地构建与验证。
3. **Adapters (多平台层)**: 将本地 Agent 自动转换为千问、Coze、百度的标准格式。
4. **Gateway (运行底座)**: 统一 API 网关，处理路由、鉴权与数据回传。

## 4. 当前阶段 (Phase 1)
- **目标**: SDK 解耦与重构。
- **交付物**: 
  - 可独立运行的 Python SDK。
  - 标准化的 `Agent Spec` 定义。
  - 基础单元测试通过。

## 5. 成功标准 (KPIs)
- **技术指标**: Context 组装延迟 < 100ms，Token 消耗降低 70%。
- **业务指标**: 跑通 "一次编写，多端发布" 流程。
