"""Root pytest configuration.

Disables pbiscan.mcp.groq_client's .env auto-loading for the entire test
session. Without this, any real `.env` file a developer happens to have at
the repo root (e.g. containing a real GROQ_API_KEY for local manual testing)
would silently make tests non-deterministic and network-dependent — worse,
E2E tests spawn `pbiscan mcp` as a real subprocess that inherits the parent
process's environment (`os.environ.copy()`), so this has to be set as an
actual environment variable, not just monkeypatched per-test, to reach both
in-process unit tests and out-of-process subprocess tests uniformly.
"""
import os

os.environ.setdefault("PBISCAN_DISABLE_DOTENV", "1")
