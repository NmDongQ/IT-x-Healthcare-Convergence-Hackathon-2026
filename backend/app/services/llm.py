from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from openai import OpenAI

client = OpenAI()

CHAT_MODEL = "gpt-4o-mini"
EVAL_MODEL = "gpt-4o-mini"

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    s = _CODE_FENCE_RE.sub("", s).strip()
    return s


def _safe_json_loads(s: str) -> Dict[str, Any]:
    s = _strip_code_fences(s)
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output")
    j = s[start : end + 1]
    return json.loads(j)


def _clamp_int(v: Any, lo: int = 0, hi: int = 3) -> int:
    try:
        x = int(v)
    except Exception:
        return lo
    return max(lo, min(hi, x))


def _clamp_float(v: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        x = float(v)
    except Exception:
        return lo
    return max(lo, min(hi, x))


def _normalize_eval(obj: Dict[str, Any]) -> Dict[str, Any]:
    semantic = obj.get("semantic_impairment", {}) if isinstance(obj.get("semantic_impairment"), dict) else {}
    info = obj.get("information_impairment", {}) if isinstance(obj.get("information_impairment"), dict) else {}
    synt = obj.get("syntactic_impairment", {}) if isinstance(obj.get("syntactic_impairment"), dict) else {}
    rationale = obj.get("rationale", {}) if isinstance(obj.get("rationale"), dict) else {}

    norm = {
        "semantic_impairment": {
            "pronoun_overuse": _clamp_int(semantic.get("pronoun_overuse", 0)),
            "vagueness": _clamp_int(semantic.get("vagueness", 0)),
            "lexical_poverty": _clamp_int(semantic.get("lexical_poverty", 0)),
            "repetition": _clamp_int(semantic.get("repetition", 0)),
        },
        "information_impairment": {
            "missing_core_info": _clamp_int(info.get("missing_core_info", 0)),
            "low_specificity": _clamp_int(info.get("low_specificity", 0)),
            "inappropriate_reference": _clamp_int(info.get("inappropriate_reference", 0)),
        },
        "syntactic_impairment": {
            "verb_reduction": _clamp_int(synt.get("verb_reduction", 0)),
            "sentence_fragments": _clamp_int(synt.get("sentence_fragments", 0)),
            "syntactic_simplification": _clamp_int(synt.get("syntactic_simplification", 0)),
        },
        "acoustic_abnormality": {"not_evaluated": True},
        "risk_probability": _clamp_float(obj.get("risk_probability", 0.0)),
        "rationale": {
            "summary": str(rationale.get("summary", ""))[:800],
            "evidence_sentences": rationale.get("evidence_sentences", [])
            if isinstance(rationale.get("evidence_sentences", []), list)
            else [],
        },
    }

    cleaned: List[str] = []
    for x in norm["rationale"]["evidence_sentences"]:
        if isinstance(x, str):
            s = x.strip()
            if s:
                cleaned.append(s[:200])
    norm["rationale"]["evidence_sentences"] = cleaned[:8]

    return norm


CHAT_SYSTEM_PROMPT = """
너는 귀엽고 친절한 어린애 말투의 통화 상대야.
사용자의 말을 잘 듣고 자연스럽게 짧게 대답해.
한 번에 1~2문장.
질문은 한 번에 하나만.
사용자의 말을 요약하거나 되묻는 것도 좋아.
""".strip()


def make_assistant_reply(conversation: List[Dict[str, str]]) -> str:
    resp = client.responses.create(
        model=CHAT_MODEL,
        temperature=0.4,
        input=[
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            *conversation,
        ],
    )
    return (resp.output_text or "").strip()


EVAL_SYSTEM_PROMPT = """
너는 의료 진단을 하지 않는다.
너의 역할은 오직 '일상 대화에서 관찰되는 언어적 위험 신호'를 구조화해 보고하는 것이다.

판단 기준:
- 의미론적 손상
- 정보 전달 손상
- 구문론적 손상

규칙:
- 점수는 0~3의 정수
- 추측 금지
- 근거는 반드시 사용자의 실제 발화에서 인용
- '치매', '질병', '진단'이라는 단어 사용 금지
- 출력은 반드시 JSON 하나만
""".strip()

EVAL_SCHEMA = """
출력 JSON 스키마(반드시 그대로의 키를 사용):
{
  "semantic_impairment": {
    "pronoun_overuse": 0,
    "vagueness": 0,
    "lexical_poverty": 0,
    "repetition": 0
  },
  "information_impairment": {
    "missing_core_info": 0,
    "low_specificity": 0,
    "inappropriate_reference": 0
  },
  "syntactic_impairment": {
    "verb_reduction": 0,
    "sentence_fragments": 0,
    "syntactic_simplification": 0
  },
  "acoustic_abnormality": {
    "not_evaluated": true
  },
  "risk_probability": 0.0,
  "rationale": {
    "summary": "",
    "evidence_sentences": []
  }
}
""".strip()


def evaluate_transcript(transcript: str, context: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    context_block = ""
    if context:
        tail = context[-6:]
        lines = []
        for m in tail:
            role = m.get("role", "")
            content = (m.get("content", "") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        if lines:
            context_block = "\n[CONTEXT]\n" + "\n".join(lines) + "\n"

    user_prompt = (
        "다음은 사용자 발화이다.\n\n"
        + context_block
        + "[TRANSCRIPT]\n"
        + (transcript or "")
        + "\n\n위 발화를 기준으로 언어적 위험 신호를 평가하라.\n"
        + EVAL_SCHEMA
    )

    resp = client.responses.create(
        model=EVAL_MODEL,
        temperature=0,
        input=[
            {"role": "system", "content": EVAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = (resp.output_text or "").strip()
    obj = _safe_json_loads(raw)
    return _normalize_eval(obj)