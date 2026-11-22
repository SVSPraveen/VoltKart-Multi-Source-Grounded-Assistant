"""backend/llm.py - Centralized LLM client with dev response cache and backoff (R-015).

Supports:
- Gemini API (v1beta generateContent) with configurable model and key.
- Dev-time persistent response cache (in data/llm_cache.json).
- Exponential backoff on rate limits (429) and server errors (5xx).
- Offline fallback capability when no API key is present.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from backend.storage import DATA_DIR, ensure_storage_dirs

CACHE_FILE = DATA_DIR / "llm_cache.json"
_DEV_CACHE: dict[str, str] = {}


def load_env_file() -> None:
    """Manually parse .env file in root directory if present without extra dependencies."""
    root_env = Path(__file__).resolve().parent.parent / ".env"
    if root_env.exists():
        try:
            for line in root_env.read_text(encoding="utf-8").splitlines():
                clean = line.strip()
                if not clean or clean.startswith("#") or "=" not in clean:
                    continue
                k, v = clean.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            pass


load_env_file()


def _get_cache_key(model: str, prompt: str, system_prompt: str, temperature: float) -> str:
    key_str = f"{model}:{temperature:.2f}:{system_prompt}:{prompt}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


def _load_cache() -> None:
    global _DEV_CACHE
    if not _DEV_CACHE and CACHE_FILE.exists():
        try:
            _DEV_CACHE = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _DEV_CACHE = {}


def _save_cache() -> None:
    ensure_storage_dirs()
    try:
        CACHE_FILE.write_text(json.dumps(_DEV_CACHE, indent=2), encoding="utf-8")
    except Exception:
        pass


def is_llm_available() -> bool:
    """Check if a Gemini API key or local Ollama instance is configured."""
    load_env_file()
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider == "ollama":
        return True
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key and key != "your_gemini_api_key_here")


def generate_llm_response(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.0,
    model: str | None = None,
    max_retries: int = 3,
) -> str | None:
    """Generate LLM completion with caching and backoff.

    Args:
        prompt: User prompt text.
        system_prompt: Optional system instruction.
        temperature: Sampling temperature (default: 0.0 for deterministic SQL/extraction).
        model: Model name (defaults to GEMINI_MODEL or gemini-2.5-flash).
        max_retries: Max retry attempts on 429/5xx.

    Returns:
        Generated text or None if offline/unavailable.
    """
    load_env_file()
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    active_model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # 1. Check dev cache first
    _load_cache()
    cache_key = _get_cache_key(active_model, prompt, system_prompt, temperature)
    if cache_key in _DEV_CACHE:
        return _DEV_CACHE[cache_key]

    # 2. Local Ollama generation
    if provider == "ollama":
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        ollama_model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        full_prompt = f"SYSTEM: {system_prompt}\n\nUSER: {prompt}" if system_prompt else prompt
        payload = {
            "model": ollama_model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(f"{ollama_base}/api/generate", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data.get("response", "")
                        _DEV_CACHE[cache_key] = text
                        _save_cache()
                        return text
            except Exception:
                time.sleep(2**attempt)
        return None

    if not api_key or api_key == "your_gemini_api_key_here":
        return None

    # 2. Call Google Generative Language API
    base_url = os.getenv(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    ).rstrip("/")
    endpoint = f"{base_url}/models/{active_model}:generateContent?key={api_key}"

    contents: list[dict[str, Any]] = []
    if system_prompt:
        contents.append(
            {"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTION:\n{system_prompt}"}]}
        )
        contents.append(
            {
                "role": "model",
                "parts": [{"text": "Understood. I will follow all instructions strictly."}],
            }
        )

    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
        },
    }

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(endpoint, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content_parts = candidates[0].get("content", {}).get("parts", [])
                        if content_parts:
                            text = content_parts[0].get("text", "")
                            # Cache successful response
                            _DEV_CACHE[cache_key] = text
                            _save_cache()
                            return text
                    return ""
                elif resp.status_code in (429, 503, 500):
                    # Rate limit or temporary service issue: exponential backoff (R-015)
                    backoff_sec = 2**attempt
                    time.sleep(backoff_sec)
                    continue
                else:
                    return None
        except Exception:
            time.sleep(2**attempt)

    return None
