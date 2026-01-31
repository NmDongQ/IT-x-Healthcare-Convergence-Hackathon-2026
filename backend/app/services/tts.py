from __future__ import annotations

from pathlib import Path

from openai import OpenAI

client = OpenAI()

# [중요] 속도가 가장 빠른 tts-1 모델로 변경
TTS_MODEL = "tts-1"
TTS_VOICE = "echo"

VOICE_INSTRUCTIONS = """
너는 트로트 가수가 무대에서 관객에게 말하듯이 응답한다.
말투는 밝고 정감 있으며, 음절 하나하나를 살려 또박또박 발음한다.
리듬을 타듯 자연스러운 억양을 사용하되 과장되지는 않는다.
속도는 빠르지 않고, 여유 있게 끌어주며 말한다.
전체적으로 노래를 부르듯 흥과 정서가 느껴지는 화법을 유지한다.
""".strip()


def synthesize_speech_to_wav(text: str, out_path: str | Path) -> str:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    audio = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text,
        response_format="wav",
    )

    out.write_bytes(audio.read())
    return str(out)