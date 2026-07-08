"""Database path configuration — isolated to avoid circular imports."""

from __future__ import annotations

from pathlib import Path

_DB_FILE = Path(__file__).resolve().parents[2] / "app_data" / "data" / "clipsay.db"
_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
DB_PATH = str(_DB_FILE)
