from __future__ import annotations

from pathlib import Path

from openai import OpenAI

client = OpenAI()

TRANSCRIBE_MODEL = "gpt-4o-mini-transcribe"


def transcribe_audio(file_path: str | Path) -> str:
    p = Path(file_path)
    if not p.exists():
        return ""

    with p.open("rb") as f:
        result = client.audio.transcriptions.create(
            model=TRANSCRIBE_MODEL,
            file=f,
        )

    text = getattr(result, "text", None)
    return (text or "").strip()