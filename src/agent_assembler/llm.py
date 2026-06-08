"""LLM 调用层 — OpenAI 兼容协议。

支持 DashScope (qwen)、OpenAI、以及任何 OpenAI-compatible 端点。
环境变量优先：
  - DASHSCOPE_API_KEY / OPENAI_API_KEY
  - OPENAI_API_BASE (默认 https://dashscope.aliyuncs.com/compatible-mode/v1)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────
# 默认配置
# ──────────────────────────────────────────

_DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen-plus"


def _get_api_key() -> str:
    """按优先级获取 API Key: DASHSCOPE > OPENAI."""
    return (
        os.environ.get("DASHSCOPE_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
    )


def _get_api_base() -> str:
    return os.environ.get("OPENAI_API_BASE", _DEFAULT_BASE)


def _get_model() -> str:
    return os.environ.get("ASSEMBLER_MODEL", _DEFAULT_MODEL)


# ──────────────────────────────────────────
# LLM 响应
# ──────────────────────────────────────────

@dataclass
class LLMResponse:
    """LLM 调用返回。"""
    content: str                        # 模型输出文本
    model: str                          # 实际使用模型
    usage: dict[str, int] = field(default_factory=dict)  # prompt/completion/total tokens
    status: str = "success"             # success | error | fallback
    error: str = ""                     # 错误信息（如有）


# ──────────────────────────────────────────
# 调用器
# ──────────────────────────────────────────

class LLMClient:
    """OpenAI 兼容 LLM 客户端。

    用法:
        client = LLMClient()
        resp = client.chat([{"role": "user", "content": "你好"}])
        print(resp.content)
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or _get_api_key()
        self.api_base = api_base or _get_api_base()
        self.model = model or _get_model()

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """发送聊天请求。

        messages: [{"role": "system|user|assistant", "content": "..."}]
        """
        if not self.api_key:
            return LLMResponse(
                content="",
                model=self.model,
                status="error",
                error="No API key. Set DASHSCOPE_API_KEY or OPENAI_API_KEY.",
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.api_base)
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            content = resp.choices[0].message.content or ""
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                "total_tokens": resp.usage.total_tokens if resp.usage else 0,
            }

            return LLMResponse(content=content, model=self.model, usage=usage)

        except ImportError:
            # openai 未安装 → 降级为 HTTP 调用
            return self._http_chat(messages, temperature, max_tokens, **kwargs)

        except Exception as e:
            return LLMResponse(
                content="", model=self.model, status="error", error=str(e)
            )

    def _http_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """不依赖 openai SDK，直接 HTTP 调用。"""
        import json
        import urllib.request
        import urllib.error

        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return LLMResponse(content=content, model=self.model, usage=usage)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else str(e)
            return LLMResponse(
                content="", model=self.model, status="error",
                error=f"HTTP {e.code}: {body}",
            )
        except Exception as e:
            return LLMResponse(
                content="", model=self.model, status="error", error=str(e)
            )

    def __repr__(self) -> str:
        key_hint = self.api_key[:8] + "..." if self.api_key else "(none)"
        return f"LLMClient(model={self.model!r}, base={self.api_base!r}, key={key_hint})"
