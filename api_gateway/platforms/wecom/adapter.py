"""企业微信卡片适配器 — 将 AA 配方输出转为企微模板卡片格式"""

def aa_to_wecom_card(aa_result: dict) -> dict:
    """AA → 企微卡片格式转换。
    
    企微卡片格式参考：https://developer.work.weixin.qq.com/document/path/90237
    """
    if not isinstance(aa_result, dict):
        return {"msgtype": "text", "text": {"content": "系统返回格式异常"}}
    
    tool_used = aa_result.get("tool_used", "智能助手")
    summary = aa_result.get("summary", "")
    
    # 企微模板卡片
    card = {
        "msgtype": "template_card",
        "template_card": {
            "card_type": "text_notice",
            "main_title": {
                "title": f"📊 {tool_used}",
                "desc": summary
            },
            "sub_title_text": _build_wecom_subtitle(aa_result),
            "button_selection": {
                "question_key": "action",
                "options": [
                    {"id": "recompute", "text": "🔄 重新计算"},
                    {"id": "guide", "text": "📋 使用指南"}
                ]
            }
        }
    }
    
    return card

def _build_wecom_subtitle(aa_result: dict) -> str:
    """构建企微副标题"""
    lines = []
    
    result = aa_result.get("result", {})
    data = result.get("data", {})
    if data:
        for key, value in list(data.items())[:3]:
            lines.append(f"{key}: {value}")
    
    suggestions = aa_result.get("next_suggestions", [])
    if suggestions:
        lines.append("\n💡 " + suggestions[0])
    
    return "\n".join(lines)
