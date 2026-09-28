"""OpenRouter client: chat (JSON), TTS and Lyria music generation."""

from __future__ import annotations

import base64
import json
import logging
import re
import time

import requests

from .config import Config

log = logging.getLogger(__name__)

RETRY_STATUS = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_BASE = 2.0


class OpenRouterError(RuntimeError):
    pass


def parse_json_lenient(text: str) -> dict:
    """Parse JSON from an LLM reply, stripping markdown code fences."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


class OpenRouter:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {cfg.api_key}",
                "X-Title": "qrated",
                "Content-Type": "application/json",
            }
        )

    def _post(self, path: str, body: dict, stream: bool = False, timeout: int = 300):
        url = f"{self.cfg.api_base}{path}"
        last: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = self.session.post(url, json=body, stream=stream, timeout=timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code not in RETRY_STATUS:
                    raise OpenRouterError(f"{path} failed: HTTP {resp.status_code} {resp.text[:300]}")
                last = OpenRouterError(f"{path} failed: HTTP {resp.status_code} {resp.text[:300]}")
            if attempt < MAX_ATTEMPTS - 1:
                delay = BACKOFF_BASE ** attempt
                log.warning("OpenRouter %s attempt %d failed (%s); retrying in %.0fs", path, attempt + 1, last, delay)
                time.sleep(delay)
        raise OpenRouterError(f"{path} failed after {MAX_ATTEMPTS} attempts: {last}")

    def chat_json(self, system: str, user: str) -> dict:
        body = {
            "model": self.cfg.llm_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = self._post("/chat/completions", body).json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError(f"unexpected chat response: {str(data)[:300]}") from exc
        return parse_json_lenient(content)

    def tts(self, text: str) -> bytes:
        body = {
            "model": self.cfg.tts_model,
            "input": text,
            "voice": self.cfg.tts_voice,
            "response_format": "mp3",
            "provider": {
                "options": {"google-ai-studio": {"speech_metadata": {"style": self.cfg.tts_style}}}
            },
        }
        return self._post("/audio/speech", body).content

    def music(self, prompt: str) -> bytes:
        body = {
            "model": self.cfg.music_model,
            "modalities": ["text", "audio"],
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = self._post("/chat/completions", body, stream=True)
        parts: list[str] = []
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            payload = raw[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                audio = chunk["choices"][0]["delta"].get("audio")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError):
                continue
            if audio and audio.get("data"):
                parts.append(audio["data"])
        if not parts:
            raise OpenRouterError("music generation returned no audio")
        return base64.b64decode("".join(parts))
