"""Decision Engine — 决策引擎（红黄绿判定）。

对 Agent 输出做质量/合规/风险判定，输出 red/yellow/green 三色 verdict。

支持三种判定模式：
1. 规则模式：关键词/正则/长度阈值
2. LLM 模式：调用 LLM 做语义判定
3. 混合模式：规则预筛 + LLM 精判
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .base import SidecarBase


@dataclass
class Rule:
    """单条判定规则。"""
    name: str
    pattern: str           # 正则表达式或关键词
    mode: str = "regex"    # regex | keyword | length_min | length_max
    verdict: str = "red"   # red | yellow | green
    description: str = ""
    severity: int = 1      # 1-3，3 最严重

    def evaluate(self, text: str) -> bool:
        """规则是否命中。"""
        if self.mode == "regex":
            return bool(re.search(self.pattern, text, re.IGNORECASE))
        elif self.mode == "keyword":
            return self.pattern.lower() in text.lower()
        elif self.mode == "length_min":
            return len(text) < int(self.pattern)
        elif self.mode == "length_max":
            return len(text) > int(self.pattern)
        return False


@dataclass
class DecisionVerdict:
    """判定结果。"""
    verdict: str = "green"           # red | yellow | green
    confidence: float = 1.0          # 0-1
    reason: str = ""
    triggered_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reason": self.reason,
            "triggered_rules": self.triggered_rules,
        }


class DecisionEngine(SidecarBase):
    """决策引擎——对 Agent 输出做"红黄绿"判定。

    用法:
        engine = DecisionEngine()
        engine.add_rule(Rule("no_personal_info", r"身份证[号码号]", "regex", "red"))
        verdict = engine.evaluate("用户的身份证号码是 110...")
        print(verdict.verdict)  # red
    """
    name = "decision"
    version = "0.2.0"

    def __init__(
        self,
        rules: list[Rule] | None = None,
        llm_client: Any | None = None,
        llm_verdict_threshold: float = 0.7,
    ):
        self._rules: list[Rule] = list(rules) if rules else []
        self._llm = llm_client
        self._llm_threshold = llm_verdict_threshold
        self._last_verdict: DecisionVerdict | None = None

        # 预置通用规则
        self._add_builtin_rules()

    def _add_builtin_rules(self):
        """添加预置规则（不覆盖用户自定义规则）。"""
        builtin = [
            Rule(
                name="too_short",
                pattern="10",
                mode="length_min",
                verdict="yellow",
                description="回复过短（<10 字符）",
                severity=1,
            ),
            Rule(
                name="error_detected",
                pattern=r"(error|错误|异常|失败|无法处理)",
                mode="regex",
                verdict="red",
                description="检测到错误/异常",
                severity=3,
            ),
            Rule(
                name="empty_response",
                pattern="5",
                mode="length_min",
                verdict="red",
                description="回复几乎为空（<5 字符）",
                severity=3,
            ),
        ]
        # 只添加不重复的规则
        existing = {r.name for r in self._rules}
        for rule in builtin:
            if rule.name not in existing:
                self._rules.append(rule)

    def add_rule(self, rule: Rule):
        """添加判定规则。"""
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """移除规则，返回是否成功。"""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def list_rules(self) -> list[dict[str, str]]:
        """列出所有规则。"""
        return [
            {"name": r.name, "mode": r.mode, "verdict": r.verdict,
             "severity": str(r.severity), "description": r.description}
            for r in self._rules
        ]

    def evaluate(self, text: str) -> DecisionVerdict:
        """对文本执行规则判定。"""
        triggered = []
        max_severity = 0
        reasons = []

        for rule in self._rules:
            if rule.evaluate(text):
                triggered.append(rule.name)
                reasons.append(f"[{rule.verdict.upper()}] {rule.name}: {rule.description}")
                max_severity = max(max_severity, rule.severity)

        # 规则判定结果
        if any(r.verdict == "red" for r in [rule for rule in self._rules if rule.name in triggered]):
            verdict = "red"
            confidence = 0.9
        elif any(r.verdict == "yellow" for r in [rule for rule in self._rules if rule.name in triggered]):
            verdict = "yellow"
            confidence = 0.7
        else:
            verdict = "green"
            confidence = 1.0

        result = DecisionVerdict(
            verdict=verdict,
            confidence=confidence,
            reason="; ".join(reasons) if reasons else "所有规则通过",
            triggered_rules=triggered,
        )

        # LLM 辅助判定（如配置）
        if self._llm is not None:
            llm_verdict = self._llm_evaluate(text)
            if llm_verdict:
                # LLM 判定与规则判定不一致 → 降级
                if llm_verdict.verdict != verdict:
                    result.verdict = "yellow"  # 不一致时降级
                    result.reason += f"; LLM 判定: {llm_verdict.verdict} ({llm_verdict.reason})"
                    result.confidence = min(result.confidence, 0.6)

        self._last_verdict = result
        return result

    def _llm_evaluate(self, text: str) -> DecisionVerdict | None:
        """调用 LLM 做语义判定。"""
        if not self._llm:
            return None

        prompt = (
            "你是一个质量判定专家。请评估以下 AI 回复的质量，"
            "给出 red/yellow/green 判定和简短理由。\n"
            "green: 高质量，完整，准确\n"
            "yellow: 有瑕疵，不完整，但不严重\n"
            "red: 严重问题，错误，违规\n\n"
            f"回复内容：\n{text[:2000]}\n\n"
            '请严格按 JSON 格式回复：{"verdict": "green|yellow|red", "reason": "简短理由"}'
        )

        try:
            resp = self._llm.chat([{"role": "user", "content": prompt}])
            if resp.status != "success":
                return None

            content = resp.content.strip()
            # 提取 JSON
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)
            verdict = data.get("verdict", "green")
            if verdict not in ("red", "yellow", "green"):
                verdict = "green"

            return DecisionVerdict(
                verdict=verdict,
                confidence=self._llm_threshold,
                reason=data.get("reason", ""),
            )
        except Exception:
            return None

    def pre_process(self, query: str) -> str:
        return query

    def post_process(self, result: dict) -> dict:
        reply = result.get("reply", "")
        if reply:
            verdict = self.evaluate(reply)
            result["decision"] = verdict.to_dict()

        return result

    @property
    def last_verdict(self) -> DecisionVerdict | None:
        return self._last_verdict

    def meta(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "rules_count": str(len(self._rules)),
            "llm_enabled": str(self._llm is not None),
        }
