from __future__ import annotations

from pathlib import Path

from openai import OpenAI

client = OpenAI()

TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "marin"

VOICE_INSTRUCTIONS = """
너는 귀엽고 밝은 어린애 톤으로 말한다.
말은 또박또박.
속도는 너무 빠르지 않게.
""".strip()


def synthesize_speech_to_wav(text: str, out_path: str | Path) -> str:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    audio = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text,
        response_format="wav",
        instructions=VOICE_INSTRUCTIONS,
    )

    out.write_bytes(audio.read())
    return str(out)