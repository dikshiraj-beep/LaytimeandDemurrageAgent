"""LLM provider layer.

Every agent step that uses the LLM calls `llm.json(...)` (structured output) or `llm.text(...)`.
If the provider is `mock`, or a call fails, the methods return None and the caller falls back to
its deterministic heuristic. This keeps the whole project runnable without an API key, while a real
model adds judgement (grading, query rewriting, vision, explanations, drafting).
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from pathlib import Path

from . import config

log = logging.getLogger("laytime.llm")


def _extract_json(text: str):
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        s, e = text.find(opener), text.rfind(closer)
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                continue
    return None


def _image_b64(path: str | Path):
    p = Path(path)
    mt = mimetypes.guess_type(p.name)[0] or "image/png"
    return mt, base64.b64encode(p.read_bytes()).decode()


class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = (provider or config.LLM_PROVIDER).lower()
        self.calls = 0
        self._client = None
        if self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic()
            self.model = config.ANTHROPIC_MODEL
        elif self.provider == "openai":
            import openai
            self._client = openai.OpenAI()
            self.model = config.OPENAI_MODEL
        elif self.provider == "azure":
            import openai
            self._client = openai.AzureOpenAI(api_version=config.AZURE_OPENAI_API_VERSION)
            self.model = config.AZURE_OPENAI_DEPLOYMENT
        else:
            self.provider, self.model = "mock", "heuristics"

    @property
    def available(self) -> bool:
        return self.provider != "mock"

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    # ------------------------------------------------------------------ core call
    def _call(self, system: str, prompt: str, images=None, max_tokens=1500) -> str | None:
        if not self.available:
            return None
        images = images or []
        self.calls += 1
        try:
            if self.provider == "anthropic":
                content = [{"type": "text", "text": prompt}]
                for img in images:
                    mt, data = _image_b64(img)
                    content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}})
                r = self._client.messages.create(
                    model=self.model, max_tokens=max_tokens, temperature=config.LLM_TEMPERATURE,
                    system=system, messages=[{"role": "user", "content": content}])
                return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            # openai + azure (chat completions)
            content = [{"type": "text", "text": prompt}]
            for img in images:
                mt, data = _image_b64(img)
                content.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{data}"}})
            r = self._client.chat.completions.create(
                model=self.model, temperature=config.LLM_TEMPERATURE, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}])
            return r.choices[0].message.content
        except Exception as e:  # network, auth, quota... -> caller falls back
            log.warning("LLM call failed (%s): %s", self.provider, e)
            return None

    def json(self, system: str, prompt: str, images=None, max_tokens=1500):
        """Returns parsed JSON (dict/list) or None."""
        out = self._call(system + "\nRespond with valid JSON only. No prose, no code fences.",
                         prompt, images, max_tokens)
        return _extract_json(out) if out else None

    def text(self, system: str, prompt: str, images=None, max_tokens=1500):
        return self._call(system, prompt, images, max_tokens)


_LLM = None


def get_llm() -> LLM:
    global _LLM
    if _LLM is None:
        _LLM = LLM()
    return _LLM
