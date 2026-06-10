"""飞书卡片适配器 — 将 AA 配方输出转为飞书消息卡片格式"""

def aa_to_feishu_card(aa_result: dict) -> dict:
    """AA → 飞书卡片格式转换。
    
    飞书卡片格式参考：https://open.feishu.cn/document/ukTMzYjL1UjM24SN0gzJ
    """
    if not isinstance(aa_result, dict):
        return {"msg_type": "text", "content": {"text": "系统返回格式异常"}}
    
    tool_used = aa_result.get("tool_used", "智能助手")
    summary = aa_result.get("summary", "")
    
    # 飞书消息卡片
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 {tool_used}"},
                "template": "blue"
            },
            "elements": _build_feishu_elements(aa_result)
        }
    }
    
    return card

def _build_feishu_elements(aa_result: dict) -> list:
    """构建飞书卡片元素"""
    elements = []
    
    # 摘要
    summary = aa_result.get("summary", "")
    if summary:
        elements.append({
            "tag": "markdown",
            "content": f"**{summary}**"
        })
    
    # 分割线
    elements.append({"tag": "hr"})
    
    # 结果表格
    result = aa_result.get("result", {})
    data = result.get("data", {})
    if data:
        table_content = "| 指标 | 数值 |\n|------|------|"
        for key, value in list(data.items())[:5]:
            table_content += f"\n| {key} | {value} |"
        elements.append({
            "tag": "markdown",
            "content": table_content
        })
    
    # 建议
    suggestions = aa_result.get("next_suggestions", [])
    if suggestions:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": "💡 **建议**:\n" + "\n".join([f"- {s}" for s in suggestions[:3]])
        })
    
    # 按钮组
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🔄 重新计算"},
                "type": "primary",
                "value": {"action": "recompute"}
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📋 使用指南"},
                "type": "default",
                "value": {"action": "guide"}
            }
        ]
    })
    
    return elements
