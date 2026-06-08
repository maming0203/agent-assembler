---
title: Agent Assembler 项目说明书 (Project Spec)
version: 1.1.0
status: Active
date: 2026-06-08
updated: 2026-06-08 (P3 文档对齐)
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
2. **SDK (开发者工具)**: 标准 Python 库 (`pip install agent-assembler`)，支持本地构建与验证。v0.3.0。
3. **Adapters (多平台层)**: 将本地 Agent 自动转换为千问、Coze、百度的标准格式。
4. **Gateway (运行底座)**: 统一 API 网关，处理路由、鉴权与数据回传。
5. **Agent/AgentSpec**: 规格驱动的 Agent 实例化（P4 新增）。
6. **Sidecar Bus**: 可热插拔的 DecisionEngine / Simulator / Analytics 插件系统（P4 新增）。
7. **Recipe Registry**: 配方搜索、标签过滤、导入导出、版本管理（P4.3 新增）。

## 4. 当前阶段 (v0.3.0 — SDK 硬化完成)
- **已完成**: P0 止血 → P1 架构拆分 → P2 Bug 修复 → P4 SDK 硬化 → P4.3 配方市场
- **进行中**: P3 文档对齐
- **规划中**: P5 SaaS Dashboard + 多平台扩展

### 4.1 交付物清单
- [x] 可独立运行的 Python SDK (`src/agent_assembler/`, 12 个公开类)
- [x] 标准化的 `AgentSpec` 定义 (dataclass)
- [x] 61/61 pytest 全绿
- [x] API Gateway 模块化 (api_gateway/, 6 模块均 <300 行)
- [x] 多平台适配器 (Coze + 千问)
- [x] Recipe Registry (搜索/标签/版本管理)

## 5. 成功标准 (KPIs)
- **技术指标**: Context 组装延迟 < 100ms，Token 消耗降低 70%。
- **业务指标**: 跑通 "一次编写，多端发布" 流程。
