"""Minimal Groq chat-completion client for the MCP `suggest_dax_rewrite` tool.

Deliberately uses only the Python standard library (`urllib`) — no new
third-party dependency, not even for the `mcp` extra. Groq's API is
OpenAI-compatible REST, so a plain POST with a Bearer token is sufficient.

BYO API key only: this module NEVER makes a network call unless the caller's
own `GROQ_API_KEY` environment variable is set. Any failure (missing key,
network error, malformed response, timeout) returns None so the caller can
fall back to the static, manually-reviewed recommendation text — this
advisory feature must never be a hard dependency for the tool to respond.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq's hosted-model catalog changes over time (models get added/retired) —
# verified live against https://api.groq.com/openai/v1/models before picking
# this default. Override with GROQ_MODEL if this one is retired later.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 15.0

_dotenv_loaded = False


def load_dotenv_if_present() -> None:
    """Load KEY=VALUE pairs from a `.env` file in the current working directory
    into os.environ, if one exists. Idempotent (runs once per process).

    Deliberately hand-rolled (no `python-dotenv` dependency) to keep this
    feature at zero new packages. Never overwrites a variable that's already
    set — an MCP host's own `env` block in its config always wins over a
    `.env` file, matching standard dotenv precedence.
    """
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True

    if os.environ.get("PBISCAN_DISABLE_DOTENV"):
        return

    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return

    try:
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError as exc:
        logger.warning("Could not read .env file at %s: %s", dotenv_path, exc)


def is_groq_configured() -> bool:
    """True if a GROQ_API_KEY is present in the environment (after loading .env)."""
    load_dotenv_if_present()
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def call_groq_chat(
    system_prompt: str,
    user_prompt: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Call Groq's chat completions endpoint and return the assistant's reply text.

    Returns None (never raises) if GROQ_API_KEY is unset, or on any network,
    HTTP, or parsing failure — callers must treat this as "AI suggestion
    unavailable, use the deterministic fallback", not as an error condition.
    """
    load_dotenv_if_present()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }

    request = urllib.request.Request(
        GROQ_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # api.groq.com sits behind Cloudflare, which can reject the default
            # urllib User-Agent ("Python-urllib/3.x") as a bot-fingerprint block
            # (HTTP 403, body "error code: 1010") before the request ever reaches
            # Groq's own auth check. A realistic UA avoids that entirely.
            "User-Agent": "pbiscan-mcp/1.0 (+https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        logger.warning("Groq API returned HTTP %s: %s", exc.code, exc.reason)
        return None
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Groq API request failed: %s", exc)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("Groq API returned an unexpected response shape: %s", exc)
        return None
