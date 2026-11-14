"""Gemini client with function calling, retries and token accounting.

The key is read from the GEMINI_API_KEY environment variable (.env). Errors are retried only
for transient HTTP codes (429/5xx); every attempt is recorded and returned so the trace shows
rate limiting honestly. A permanent failure raises LLMError - there is no mock fallback.
"""
import os
import random
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from .config import ROOT

DEFAULT_MODEL = "gemini-3.5-flash-lite"
RETRY_CODES = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    def __init__(self, message: str, attempts: list[dict]) -> None:
        super().__init__(message)
        self.attempts = attempts


class GeminiLLM:
    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = 0.0,
                 max_attempts: int = 5, base_delay: float = 2.0) -> None:
        load_dotenv(ROOT / ".env")
        self._key = os.environ.get("GEMINI_API_KEY")
        if not self._key:
            raise RuntimeError("GEMINI_API_KEY is not set; put it in .env (see .env.example)")
        self.client = genai.Client(api_key=self._key)
        self.model, self.temperature = model, temperature
        self.max_attempts, self.base_delay = max_attempts, base_delay

    def _redact(self, text: str) -> str:
        return text.replace(self._key, "<key>")[:1200]

    def generate(self, contents: list[types.Content], system: str,
                 declarations: list[types.FunctionDeclaration]) -> dict[str, Any]:
        cfg = types.GenerateContentConfig(
            system_instruction=system, temperature=self.temperature,
            tools=[types.Tool(function_declarations=declarations)],
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY")),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        attempts: list[dict] = []
        for i in range(self.max_attempts):
            t0 = time.perf_counter()
            try:
                r = self.client.models.generate_content(model=self.model, contents=contents, config=cfg)
            except errors.APIError as e:
                attempts.append({"attempt": i + 1, "code": e.code, "message": self._redact(str(e)),
                                 "elapsed_ms": round((time.perf_counter() - t0) * 1000)})
                if e.code not in RETRY_CODES or i == self.max_attempts - 1:
                    raise LLMError(f"Gemini API error {e.code}", attempts) from e
                time.sleep(min(60.0, self.base_delay * 2 ** i) + random.random())
                continue
            if not r.candidates or r.candidates[0].content is None or not r.candidates[0].content.parts:
                reason = r.candidates[0].finish_reason if r.candidates else "no candidates"
                raise LLMError(f"empty model response ({reason})", attempts)
            u = r.usage_metadata
            return {
                "content": r.candidates[0].content,
                "calls": [(p.function_call.name, dict(p.function_call.args or {}))
                          for p in r.candidates[0].content.parts if p.function_call],
                "text": "".join(p.text for p in r.candidates[0].content.parts if p.text and not p.thought),
                "usage": {"prompt_tokens": u.prompt_token_count or 0,
                          "output_tokens": u.candidates_token_count or 0,
                          "thought_tokens": getattr(u, "thoughts_token_count", None) or 0},
                "attempts": attempts,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000)}
        raise LLMError("unreachable", attempts)
