"""Small async OpenRouter client for Gemini Flash prompts."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("algo-openrouter")

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0, 2.0)


class OpenRouterClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("OPENROUTER_MODEL", "google/gemini-flash-1.5")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "http://localhost:3000")
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "Algo Interview Agent")

    async def chat(self, system: str, user: str, *, temperature: float = 0.35, max_tokens: int = 700) -> str:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set.")

        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=25) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions", json=payload, headers=headers
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                if status < 500:
                    raise  # do not retry client (4xx) errors
            except httpx.HTTPError as exc:
                last_exc = exc

            if attempt < _MAX_ATTEMPTS - 1:
                delay = _BACKOFF_SECONDS[attempt]
                logger.warning(
                    "OpenRouter chat attempt %d/%d failed (%s); retrying in %.1fs.",
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    last_exc,
                    delay,
                )
                await asyncio.sleep(delay)

        assert last_exc is not None
        raise last_exc

    async def json_chat(self, system: str, user: str, *, fallback: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = await self.chat(system, user, temperature=0.1, max_tokens=650)
        except httpx.HTTPError as exc:
            logger.warning("OpenRouter json_chat failed after retries (%s); using fallback.", exc)
            return fallback
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return fallback
