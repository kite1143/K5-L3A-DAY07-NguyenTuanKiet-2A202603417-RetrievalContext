"""Adapter gọi model thật qua HTTP; không có nhánh mock.

Hỗ trợ:
  * openai  - mọi endpoint tương thích OpenAI (/chat/completions): OpenAI,
              OpenRouter, DeepSeek, Groq, vLLM, LM Studio...
  * ollama  - /api/chat của Ollama chạy local.

Cấu hình đọc từ biến môi trường (không hard-code key):

    DAY7_LLM_PROVIDER=openai|ollama
    DAY7_LLM_MODEL=<tên model>
    DAY7_LLM_BASE_URL=<url gốc, ví dụ https://api.openai.com/v1>
    DAY7_LLM_API_KEY=<key>          # hoặc OPENAI_API_KEY / OPENROUTER_API_KEY
    DAY7_LLM_TIMEOUT=60
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://127.0.0.1:11434",
}
KEY_ENV_FALLBACKS = ("DAY7_LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY")


class ProviderError(RuntimeError):
    """Lỗi gọi model; được ghi vào trace với status 'error', không thay bằng kết quả giả."""


def _post_json(url: str, payload: dict, *, headers: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise ProviderError(f"HTTP {exc.code} từ {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"không kết nối được {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError(f"response không phải JSON từ {url}: {exc}") from exc


class OpenAICompatibleModel:
    provider = "openai"

    def __init__(self, model: str, *, api_key: str, base_url: str = DEFAULT_BASE_URLS["openai"], timeout: float = 60.0) -> None:
        if not api_key:
            raise ValueError("thiếu API key cho provider openai")
        if not model:
            raise ValueError("thiếu tên model")
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[dict], *, temperature: float = 0.0, max_tokens: int = 900) -> dict:
        started = time.perf_counter()
        response = _post_json(
            f"{self.base_url}/chat/completions",
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        try:
            text = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"response thiếu choices[0].message.content: {response}") from exc
        usage = response.get("usage") or {}
        return {
            "text": text or "",
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            },
            "latency_ms": (time.perf_counter() - started) * 1000,
            "model": response.get("model") or self.model,
        }


class OllamaModel:
    provider = "ollama"

    def __init__(self, model: str, *, base_url: str = DEFAULT_BASE_URLS["ollama"], timeout: float = 120.0) -> None:
        if not model:
            raise ValueError("thiếu tên model ollama")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[dict], *, temperature: float = 0.0, max_tokens: int = 900) -> dict:
        started = time.perf_counter()
        response = _post_json(
            f"{self.base_url}/api/chat",
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            headers={},
            timeout=self.timeout,
        )
        text = (response.get("message") or {}).get("content", "")
        return {
            "text": text or "",
            "usage": {
                "prompt_tokens": response.get("prompt_eval_count"),
                "completion_tokens": response.get("eval_count"),
            },
            "latency_ms": (time.perf_counter() - started) * 1000,
            "model": response.get("model") or self.model,
        }


def model_from_env(environ: dict | None = None):
    env = environ if environ is not None else os.environ
    provider = (env.get("DAY7_LLM_PROVIDER") or "openai").strip().lower()
    model = (env.get("DAY7_LLM_MODEL") or "").strip()
    timeout = float(env.get("DAY7_LLM_TIMEOUT") or 60)
    if provider == "ollama":
        base_url = env.get("DAY7_LLM_BASE_URL") or DEFAULT_BASE_URLS["ollama"]
        return OllamaModel(model, base_url=base_url, timeout=timeout)
    if provider not in ("openai", "openrouter", "deepseek", "groq", "vllm", "lmstudio"):
        raise ValueError(f"provider không hỗ trợ: {provider!r}")
    api_key = next((env[name] for name in KEY_ENV_FALLBACKS if env.get(name)), "")
    base_url = env.get("DAY7_LLM_BASE_URL") or DEFAULT_BASE_URLS.get(provider, DEFAULT_BASE_URLS["openai"])
    return OpenAICompatibleModel(model, api_key=api_key, base_url=base_url, timeout=timeout)
