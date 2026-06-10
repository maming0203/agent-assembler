"""钉钉卡片适配器 — 将 AA 配方输出转为钉钉互动卡片格式"""

def aa_to_dingtalk_card(aa_result: dict) -> dict:
    """AA → 钉钉卡片格式转换。
    
    钉钉卡片格式参考：https://open.dingtalk.com/document/orgapp/message-card-overview
    """
    if not isinstance(aa_result, dict):
        return {"msgtype": "text", "text": {"content": "系统返回格式异常"}}
    
    status = aa_result.get("status", "error")
    tool_id = aa_result.get("tool_id", "unknown")
    summary = aa_result.get("summary", "")
    
    # 钉钉 Markdown 卡片
    card = {
        "msgtype": "actionCard",
        "actionCard": {
            "title": f"📊 {aa_result.get('tool_used', '智能助手')}",
            "text": _build_dingtalk_markdown(aa_result),
            "btnOrientation": "0",  # 竖向排列
            "btns": [
                {"title": "🔄 重新计算", "actionURL": "dtalk://recompute"},
                {"title": "📋 使用指南", "actionURL": "dtalk://guide"}
            ]
        }
    }
    
    return card

def _build_dingtalk_markdown(aa_result: dict) -> str:
    """构建钉钉 Markdown 内容"""
    lines = []
    
    # 标题
    tool_used = aa_result.get("tool_used", "智能助手")
    lines.append(f"### 📊 {tool_used}\n")
    
    # 摘要
    summary = aa_result.get("summary", "")
    if summary:
        lines.append(f"**{summary}**\n")
    
    # 结果表格
    result = aa_result.get("result", {})
    data = result.get("data", {})
    if data:
        lines.append("\n| 指标 | 数值 |")
        lines.append("|------|------|")
        for key, value in list(data.items())[:5]:  # 最多5行
            lines.append(f"| {key} | {value} |")
    
    # 建议
    suggestions = aa_result.get("next_suggestions", [])
    if suggestions:
        lines.append("\n💡 **建议**:")
        for s in suggestions[:3]:
            lines.append(f"- {s}")
    
    return "\n".join(lines)
