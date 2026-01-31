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


# --- CHAT / TURN MANAGEMENT ---

CHAT_SYSTEM_PROMPT = """
너는 시골에 사시는 어르신에게 안부 전화를 건 '건강지킴이'야.
손주나 딸처럼 친근하고 밝은 말투(반말/존댓말 섞어서 자연스럽게)를 써.
어르신의 건강, 식사, 기분 등을 물어봐.
한 번에 1~2문장으로 짧게 대답해.

[중요]
대화가 마무리될 때나 어르신이 그만 끊자고 하면
마무리 인사를 하고 문장 맨 끝에 반드시 "[END]"라고 붙여.
""".strip()


def make_assistant_reply(conversation: List[Dict[str, str]]) -> tuple[str, bool]:
    """
    Returns: (reply_text, end_call_flag)
    """
    
    # [수정] 대화 길이 강제 제한 로직
    # conversation 리스트 길이 6 = (User, AI) x 3턴
    is_time_to_end = len(conversation) >= 6
    
    current_prompt = CHAT_SYSTEM_PROMPT
    if is_time_to_end:
        current_prompt += "\n\n[SYSTEM: 대화가 충분히 길어졌어. 이제 다정하게 작별 인사를 하고 반드시 문장 끝에 [END]를 붙여서 통화를 종료해.]"

    # [수정] 올바른 OpenAI 메서드 사용
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": current_prompt},
            *conversation,
        ],
        temperature=0.7,
    )
    raw_text = (resp.choices[0].message.content or "").strip()

    end_call = False
    if "[END]" in raw_text:
        end_call = True
        raw_text = raw_text.replace("[END]", "").strip()

    return raw_text, end_call


# --- EVALUATION (PER TURN) ---

EVAL_SYSTEM_PROMPT = """
너는 의료 진단을 하지 않는다.
너의 역할은 오직 '일상 대화에서 관찰되는 언어적 위험 신호'를 구조화해 보고하는 것이다.

판단 기준:
- 의미론적 손상 (대명사 과다, 모호함 등)
- 정보 전달 손상 (핵심 정보 누락 등)
- 구문론적 손상 (문장 파편화 등)

규칙:
- 점수는 0~3의 정수
- 추측 금지
- 근거는 반드시 사용자의 실제 발화에서 인용
- '치매', '질병', '진단'이라는 단어 사용 금지
- 출력은 반드시 JSON 하나만
""".strip()

EVAL_SCHEMA = """
출력 JSON 스키마:
{
  "semantic_impairment": { "pronoun_overuse": 0, "vagueness": 0, "lexical_poverty": 0, "repetition": 0 },
  "information_impairment": { "missing_core_info": 0, "low_specificity": 0, "inappropriate_reference": 0 },
  "syntactic_impairment": { "verb_reduction": 0, "sentence_fragments": 0, "syntactic_simplification": 0 },
  "acoustic_abnormality": { "not_evaluated": true },
  "risk_probability": 0.0,
  "rationale": { "summary": "", "evidence_sentences": [] }
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

    resp = client.chat.completions.create(
        model=EVAL_MODEL,
        messages=[
            {"role": "system", "content": EVAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={ "type": "json_object" },
        temperature=0,
    )

    raw = (resp.choices[0].message.content or "").strip()
    try:
        obj = _safe_json_loads(raw)
    except Exception:
        # 실패 시 기본값
        return {
            "risk_probability": 0.0, 
            "rationale": {"summary": "분석 실패", "evidence_sentences": []}
        }
    return _normalize_eval(obj)


# --- FINAL REPORT ---

REPORT_SYSTEM_PROMPT = """
너는 노인 인지 건강 관리 전문가야.
사용자와 AI의 전체 통화 내용을 바탕으로 종합 보고서를 작성해.
치매 위험 징후가 있었는지, 대화 흐름은 어땠는지 요약해줘.
JSON 포맷으로 출력해.
""".strip()

REPORT_SCHEMA = """
{
  "final_risk_score": 0.0,
  "summary_text": "전체적인 대화 요약 및 특이사항..."
}
""".strip()

def generate_final_report(conversation: List[Dict[str, str]]) -> Dict[str, Any]:
    # 전체 대화 텍스트화
    lines = []
    for turn in conversation:
        r = turn.get("role", "unknown")
        t = turn.get("content", "")
        lines.append(f"{r}: {t}")
    full_text = "\n".join(lines)

    user_prompt = (
        "다음은 전체 통화 내역이다.\n"
        + full_text
        + "\n\n위 내용을 바탕으로 인지 건강 관점의 종합 리포트를 작성하라.\n"
        + REPORT_SCHEMA
    )

    resp = client.chat.completions.create(
        model=EVAL_MODEL,
        messages=[
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={ "type": "json_object" },
        temperature=0,
    )
    
    raw = (resp.choices[0].message.content or "").strip()
    try:
        return _safe_json_loads(raw)
    except:
        return {"final_risk_score": 0.0, "summary_text": "리포트 생성 실패"}