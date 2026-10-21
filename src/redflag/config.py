"""Paths and environment configuration. No secrets are stored in the repository."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_CASES = ROOT / "data" / "cases"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

#: SEC fair-access policy allows at most 10 requests per second; stay below that.
MAX_REQUESTS_PER_SECOND = 8


def _read_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env reader (KEY=value lines); avoids an extra dependency."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_user_agent() -> str:
    """Return the SEC User-Agent from the environment or a gitignored .env file.

    Raises
    ------
    RuntimeError
        If ``SEC_USER_AGENT`` is not configured. SEC rejects anonymous automated clients.
    """
    value = os.environ.get("SEC_USER_AGENT") or _read_dotenv(ROOT / ".env").get("SEC_USER_AGENT")
    if not value:
        raise RuntimeError(
            "SEC_USER_AGENT is not set. Export it or put it in a gitignored .env file, "
            'e.g. SEC_USER_AGENT="Your Name your.email@example.com" (see .env.example).'
        )
    return value
