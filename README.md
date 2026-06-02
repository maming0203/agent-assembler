# Agent Assembler

JIT (Just-In-Time) 上下文组装中间件。通过「配方 (Recipe) + 原子技能 (Skill)」模式，实现确定性、低延迟、防幻觉的 AI Agent 交付。

## 核心架构

- **Recipe-First**: 优先匹配本地配方库 (200+ Recipes)，未命中时触发 Auto-Craft 动态生成。
- **JIT Context Assembly**: 按需加载 Skill，拒绝全量加载，降低 Token 消耗与幻觉风险。
- **Container Hardening**: 文档写入强制脚本，防止数字尘埃。

## 快速开始

### 1. 启动 API Gateway

```bash
# 安装依赖
pip install fastapi uvicorn pydantic

# 启动服务
python api_gateway.py
# 或使用 uvicorn
uvicorn api_gateway:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 测试接口

```bash
# 登录获取 API Key
curl http://localhost:8000/api/v1/login?device_id=test_user

# 执行查询 (配方匹配 + Agent 执行)
curl -X POST http://localhost:8000/api/v1/run \
  -H "x-api-key: YOUR_KEY" \
  -H "content-type: application/json" \
  -d '{"query": "帮我策划一个年会"}'
```

## 目录结构

- `api_gateway.py`: 核心网关服务，处理 Login/Run 路由、Recipe 匹配、Skill 加载。
- `agent_assembler/`: Python SDK 源码（Assembler 引擎、Recipe 解析器）。
- `tests/`: 单元测试。

## 部署

支持本地运行或 Docker 化部署。云端部署时会自动切换为云端路径模式 (`IS_CLOUD=True`)。
