from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select, or_
from sqlalchemy.orm import Session as DBSession

# 통합된 DB 및 모델 사용
from .db import get_db, SessionLocal, engine, Base, STORAGE_DIR
from .models import Session as SessionModel, Turn as TurnModel, Member as MemberModel

from .services.llm import evaluate_transcript, make_assistant_reply, generate_final_report
from .services.stt import transcribe_audio
from .services.tts import synthesize_speech_to_wav

AUDIO_DIR = STORAGE_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# 테이블 생성 (models.py 정의 기반)
Base.metadata.create_all(engine)

router = APIRouter()

# 헬퍼: DB 세션 생성
def db() -> DBSession:
    return SessionLocal()

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _get_session_or_404(s: DBSession, session_id: str) -> SessionModel:
    row = s.get(SessionModel, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    return row

def _next_turn_index(s: DBSession, session_id: str) -> int:
    q = select(TurnModel.turn_index).where(TurnModel.session_id == session_id).order_by(TurnModel.turn_index.desc()).limit(1)
    last = s.execute(q).scalar_one_or_none()
    return int(last + 1) if last is not None else 1

def _load_recent_conversation(s: DBSession, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
    q = (
        select(TurnModel)
        .where(TurnModel.session_id == session_id)
        .order_by(TurnModel.turn_index.asc())
    )
    rows = s.execute(q).scalars().all()
    # 전체 맥락을 위해 limit을 좀 넉넉히 잡거나, 필요하면 슬라이싱
    subset = rows[-limit:] if len(rows) > limit else rows

    convo: List[Dict[str, str]] = []
    for r in rows:
        if not r.text:
            continue
        role = "user" if r.speaker == "user" else "assistant"
        convo.append({"role": role, "content": r.text})
    return convo # 전체 대화 반환

# --- API ENDPOINTS ---

@router.post("/session/start")
def start_session(device_info: str = Form(default="")) -> Dict[str, Any]:
    session_id = secrets.token_hex(8)
    started = now_utc_iso()

    with db() as s:
        row = SessionModel(
            session_id=session_id,
            device_info=device_info[:200] if device_info else None,
            started_at_utc=started,
            ended_at_utc=None,
        )
        s.add(row)
        s.commit()

    return {"session_id": session_id, "started_at_utc": started}

@router.post("/session/end")
def end_session(session_id: str = Form(...)) -> Dict[str, Any]:
    with db() as s:
        row = _get_session_or_404(s, session_id)
        row.ended_at_utc = now_utc_iso()
        s.commit()
        # commit 후에는 객체가 만료되므로 필요한 데이터만 리턴하거나 refresh 해야 함
        return {"session_id": session_id, "ended_at_utc": now_utc_iso()}

@router.post("/session/{session_id}/finalize")
def finalize_session_endpoint(session_id: str) -> Dict[str, Any]:
    """
    통화 종료 후 종합 리포트 생성 및 DB 영구 저장
    """
    with db() as s:
        row = _get_session_or_404(s, session_id)
        
        # 아직 종료 시간이 없으면 기록
        if not row.ended_at_utc:
            row.ended_at_utc = now_utc_iso()
        
        # 1. 전체 대화 로드
        convo = _load_recent_conversation(s, session_id, limit=100)
        
        # 2. 리포트 생성 (LLM)
        report_data = generate_final_report(convo)
        
        # 3. DB에 저장 (JSON 문자열로 변환)
        row.final_report = json.dumps(report_data, ensure_ascii=False)
        s.commit()
        
        # 4. 응답 데이터 준비 (세션 종료 후 객체 접근 방지를 위해 변수에 담기)
        # DetachedInstanceError 방지를 위해 값 복사
        response_data = {
            "session_id": row.session_id,
            "ended_at_utc": row.ended_at_utc,
            "report": report_data
        }

    return response_data

@router.get("/session/{session_id}/report")
def get_session_report(session_id: str) -> Dict[str, Any]:
    """
    저장된 리포트 조회 (다른 프론트엔드에서 사용 가능)
    """
    with db() as s:
        row = _get_session_or_404(s, session_id)
        report = None
        if row.final_report:
            try:
                report = json.loads(row.final_report)
            except:
                report = {"error": "Invalid JSON format"}
        
        return {
            "session_id": row.session_id,
            "report": report
        }

@router.post("/turn/user")
def user_turn(
    session_id: str = Form(...),
    start_ms: int = Form(...),
    end_ms: int = Form(...),
    audio: UploadFile = File(...),
) -> Dict[str, Any]:
    if end_ms < start_ms:
        raise HTTPException(status_code=400, detail="end_ms must be >= start_ms")

    with db() as s:
        _get_session_or_404(s, session_id)

        idx = _next_turn_index(s, session_id)

        # 확장자 처리
        original_ext = Path(audio.filename or "").suffix.lower()
        if not original_ext:
            original_ext = ".webm"
            
        fname = f"{session_id}_user_{uuid.uuid4().hex}{original_ext}"
        out_path = AUDIO_DIR / fname

        data = audio.file.read()
        out_path.write_bytes(data)

        # STT
        transcript = transcribe_audio(out_path)
        if not transcript:
            transcript = "(전사 실패)"

        # 평가
        context = _load_recent_conversation(s, session_id, limit=10)
        llm_eval = evaluate_transcript(transcript, context=context)
        risk_prob = float(llm_eval.get("risk_probability", 0.0))
        
        meta = {
            "llm_evaluation": llm_eval,
            "risk_prob": risk_prob,
        }

        row = TurnModel(
            session_id=session_id,
            turn_index=idx,
            speaker="user",
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            text=transcript,
            audio_path=str(out_path),
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
        s.add(row)
        s.commit()

        return {
            "turn_index": idx,
            "speaker": "user",
            "start_ms": int(start_ms),
            "end_ms": int(end_ms),
            "transcript": transcript,
            "risk_prob": risk_prob,
            "audio_path": str(out_path),
            "audio_url": f"/storage/audio/{out_path.name}",
        }


@router.post("/turn/assistant")
def assistant_turn(
    session_id: str = Form(...),
    start_ms: int = Form(...),
    end_ms: int = Form(...),
) -> Dict[str, Any]:
    with db() as s:
        _get_session_or_404(s, session_id)
        idx = _next_turn_index(s, session_id)
        convo = _load_recent_conversation(s, session_id, limit=20)
        
        tts_text, end_call = make_assistant_reply(convo)
        if not tts_text:
            tts_text = "응? 다시 말해줄래?"

        fname = f"{session_id}_assistant_{uuid.uuid4().hex}.wav"
        out_path = AUDIO_DIR / fname
        synthesize_speech_to_wav(tts_text, out_path)

        meta = {"end_call": end_call}

        row = TurnModel(
            session_id=session_id,
            turn_index=idx,
            speaker="assistant",
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            text=tts_text,
            audio_path=str(out_path),
            meta_json=json.dumps(meta),
        )
        s.add(row)
        s.commit()

        return {
            "turn_index": idx,
            "speaker": "assistant",
            "tts_text": tts_text,
            "audio_path": str(out_path),
            "audio_url": f"/storage/audio/{out_path.name}",
            "meta_json": meta,
        }

# --- EXPORT & MEMBER API ---

@router.get("/session/{session_id}/export/txt")
def export_txt(session_id: str) -> PlainTextResponse:
    with db() as s:
        _get_session_or_404(s, session_id)
        q = select(TurnModel).where(TurnModel.session_id == session_id).order_by(TurnModel.turn_index.asc())
        rows = s.execute(q).scalars().all()

    lines = []
    for r in rows:
        lines.append(f"[{r.start_ms/1000:.1f}s] {r.speaker}: {r.text or ''}")
    return PlainTextResponse("\n".join(lines))

@router.get("/members")
def list_members(search: str = "", limit: int = 200, offset: int = 0) -> Dict[str, Any]:
    with db() as s:
        q = select(MemberModel)
        if search.strip():
            key = f"%{search.strip()}%"
            q = q.where(
                (MemberModel.member_no.like(key)) |
                (MemberModel.customer_name.like(key))
            )
        q = q.limit(limit).offset(offset)
        rows = s.execute(q).scalars().all()

    items = []
    for r in rows:
        items.append({
            "memberNo": r.member_no,
            "customerName": r.customer_name,
            "guardianName": r.guardian_name,
            "risk": r.risk,
            "customerPhone": r.customer_phone,
            "guardianPhone": r.guardian_phone,
        })
    return {"items": items, "count": len(items)}

@router.post("/members/seed")
def seed_members() -> Dict[str, Any]:
    name_pool = ["김*준","박*준","이*지","최*연","정*우"]
    # ... (간소화) ...
    
    with db() as s:
        # 이미 데이터가 있으면 pass
        if s.execute(select(MemberModel).limit(1)).scalar_one_or_none():
            return {"inserted": 0}

        for i in range(10):
            m = MemberModel(
                member_no=str(1000+i),
                customer_name=name_pool[i%5],
                guardian_name="보호자"+str(i),
                risk=50+i,
                customer_phone="010-0000-0000",
                guardian_phone="010-1111-1111",
                created_at_utc=now_utc_iso()
            )
            s.add(m)
        s.commit()
    return {"inserted": 10}