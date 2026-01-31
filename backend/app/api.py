from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import func, select

from .db import get_db
from .models import Session as DbSession, Turn
from .storage import new_audio_path, ensure_dirs

router = APIRouter()


def utcnow():
    return datetime.now(timezone.utc)


def require_session(db: OrmSession, session_id: str) -> DbSession:
    s = db.get(DbSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return s


def next_turn_index(db: OrmSession, session_id: str) -> int:
    # turn_index는 1부터 시작
    q = select(func.max(Turn.turn_index)).where(Turn.session_id == session_id)
    m = db.execute(q).scalar()
    return int(m or 0) + 1


@router.post("/session/start")
def session_start(
    device_info: str | None = Form(default=None),
    db: OrmSession = Depends(get_db),
):
    session_id = uuid4().hex[:16]
    s = DbSession(
        id=session_id,
        started_at_utc=utcnow(),
        ended_at_utc=None,
        device_info=device_info,
    )
    db.add(s)
    db.commit()
    return {"session_id": session_id, "started_at_utc": s.started_at_utc.isoformat()}


@router.post("/turn/user")
async def turn_user(
    session_id: str = Form(...),
    start_ms: int = Form(...),
    end_ms: int = Form(...),
    audio: UploadFile = File(...),
    db: OrmSession = Depends(get_db),
):
    # 세션 확인
    require_session(db, session_id)

    if end_ms < start_ms:
        raise HTTPException(status_code=400, detail="end_ms must be >= start_ms")

    ensure_dirs()

    # 파일 저장
    ext = (audio.filename.split(".")[-1] if audio.filename and "." in audio.filename else "wav").lower()
    out_path: Path = new_audio_path(session_id=session_id, speaker="user", ext=ext)
    content = await audio.read()
    out_path.write_bytes(content)

    # 전사: 지금은 더미
    transcript = "(transcript pending)"

    idx = next_turn_index(db, session_id)
    t = Turn(
        session_id=session_id,
        turn_index=idx,
        speaker="user",
        start_ms=start_ms,
        end_ms=end_ms,
        text=transcript,
        audio_path=str(out_path),
        meta_json=None,
    )
    db.add(t)
    db.commit()

    return {
        "turn_index": idx,
        "speaker": "user",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "transcript": transcript,
        "audio_path": str(out_path),
    }


@router.post("/turn/assistant")
def turn_assistant(
    session_id: str = Form(...),
    start_ms: int = Form(...),
    end_ms: int = Form(...),
    db: OrmSession = Depends(get_db),
):
    require_session(db, session_id)

    if end_ms < start_ms:
        raise HTTPException(status_code=400, detail="end_ms must be >= start_ms")

    # LLM: 지금은 더미(짧게)
    tts_text = "안녕! 지금부터 간단한 질문을 해볼게. 오늘은 무슨 요일이야?"

    # TTS: 지금은 더미 음성파일 생성 대신, 텍스트만 반환해도 되지만
    # RN에서 재생 테스트를 위해, 일단 빈 파일이라도 만들어 둠
    ensure_dirs()
    out_path: Path = new_audio_path(session_id=session_id, speaker="assistant", ext="wav")
    out_path.write_bytes(b"")  # TODO: 실제 TTS로 교체

    idx = next_turn_index(db, session_id)
    t = Turn(
        session_id=session_id,
        turn_index=idx,
        speaker="assistant",
        start_ms=start_ms,
        end_ms=end_ms,
        text=tts_text,
        audio_path=str(out_path),
        meta_json=None,
    )
    db.add(t)
    db.commit()

    return {
        "turn_index": idx,
        "speaker": "assistant",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "tts_text": tts_text,
        "audio_path": str(out_path),
    }


def ms_to_mmss(ms: int) -> str:
    if ms < 0:
        ms = 0
    sec = ms // 1000
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}.{ms%1000:03d}"


@router.get("/session/{session_id}/export/txt")
def export_txt(session_id: str, db: OrmSession = Depends(get_db)):
    require_session(db, session_id)

    turns = (
        db.query(Turn)
        .filter(Turn.session_id == session_id)
        .order_by(Turn.turn_index.asc())
        .all()
    )

    lines = []
    for t in turns:
        st = ms_to_mmss(t.start_ms)
        ed = ms_to_mmss(t.end_ms)
        who = t.speaker
        text = t.text or ""
        lines.append(f"[{st} - {ed}] {who}: {text}")

    return PlainTextResponse("\n".join(lines) + "\n")


@router.get("/session/{session_id}/export/json")
def export_json(session_id: str, db: OrmSession = Depends(get_db)):
    s = require_session(db, session_id)

    turns = (
        db.query(Turn)
        .filter(Turn.session_id == session_id)
        .order_by(Turn.turn_index.asc())
        .all()
    )

    payload = {
        "session_id": s.id,
        "started_at_utc": s.started_at_utc.isoformat(),
        "ended_at_utc": s.ended_at_utc.isoformat() if s.ended_at_utc else None,
        "turns": [
            {
                "turn_index": t.turn_index,
                "speaker": t.speaker,
                "start_ms": t.start_ms,
                "end_ms": t.end_ms,
                "text": t.text,
                "audio_path": t.audio_path,
                "meta_json": t.meta_json,
            }
            for t in turns
        ],
    }
    return JSONResponse(payload)