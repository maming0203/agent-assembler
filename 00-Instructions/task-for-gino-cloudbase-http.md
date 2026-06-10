# Task: 开启 Gateway 函数 HTTP 访问 (Task 001)

## 背景
Hermes 无法直接访问腾讯云控制台。为了接入微信 AI (AIO)，我们需要为 `gateway` 云函数开启公网 HTTP 访问。

## 操作目标
在 CloudBase 控制台中，为 `agent-assembler-d2fw0i3icd74dfb4` 环境的 `gateway` 函数添加 HTTP Web 触发器。

## 执行步骤 (Gino 请执行)
1. **登录**：访问 https://tcb.cloud.tencent.com/dev ，扫码登录。
2. **定位函数**：进入 云函数/托管/主机 -> 云函数列表 -> 找到 `gateway` 函数。
3. **配置触发器**：
   - 点击 `gateway` -> 触发管理。
   - 点击 **新建触发器**。
   - **触发方式**：选择 `HTTP 服务触发` (Web 访问)。
   - **路径**：填写 `/gateway`。
   - **请求方法**：勾选 `POST` (建议也勾选 `GET` 用于测试)。
   - **启用鉴权**：暂时**不开启** (或开启但记下 Key)，确保外部可通。
4. **获取 URL**：保存后，复制生成的公网 URL (类似 `https://xxx.service.tcloudbase.com/gateway`)。

## 交付物
- 将生成的 **HTTP URL** 返回给 Hermes (写入 `HEARTBEAT.md` 或直接发消息)。
