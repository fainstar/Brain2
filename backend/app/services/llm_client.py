from __future__ import annotations

from typing import List

import httpx

from app.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.chat_model = settings.llm_chat_model
        self.embed_model = settings.llm_embed_model
        self.timeout = settings.llm_timeout_seconds

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> List[float]:
        payload = {"model": self.embed_model, "input": text}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    async def ping(self) -> bool:
        payload = {
            "model": self.chat_model,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                return res.status_code == 200
        except Exception:
            return False
