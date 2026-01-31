# backend/app/storage.py
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

STORAGE_DIR = Path("./storage")
AUDIO_DIR = STORAGE_DIR / "audio"


def ensure_dirs():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def new_audio_path(session_id: str, speaker: str, ext: str = "wav") -> Path:
    ensure_dirs()
    fname = f"{session_id}_{speaker}_{uuid4().hex}.{ext}"
    return AUDIO_DIR / fname