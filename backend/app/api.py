from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, select, or_
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from .models import Member
from .db import get_db

from .services.llm import evaluate_transcript, make_assistant_reply
from .services.stt import transcribe_audio
from .services.tts import synthesize_speech_to_wav

Base = declarative_base()

ROOT_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = ROOT_DIR / "storage"
AUDIO_DIR = STORAGE_DIR / "audio"
DB_PATH = STORAGE_DIR / "app.sqlite3"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionRow(Base):
    __tablename__ = "sessions"
    session_id = Column(String(32), primary_key=True)
    device_info = Column(String(200), nullable=True)
    started_at_utc = Column(String(40), nullable=False)
    ended_at_utc = Column(String(40), nullable=True)

    turns = relationship("TurnRow", back_populates="session", cascade="all, delete-orphan")


class TurnRow(Base):
    __tablename__ = "turns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.session_id"), index=True, nullable=False)
    turn_index = Column(Integer, nullable=False)
    speaker = Column(String(16), nullable=False)  # "user" or "assistant"
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    audio_path = Column(String(500), nullable=True)
    meta_json = Column(Text, nullable=True)

    session = relationship("SessionRow", back_populates="turns")

class MemberRow(Base):
    __tablename__ = "members"

    member_no = Column(String(32), primary_key=True)  # 회원번호
    customer_name = Column(String(50), nullable=False)
    guardian_name = Column(String(50), nullable=False)
    risk = Column(Integer, nullable=False)  # 0~100
    customer_phone = Column(String(30), nullable=False)
    guardian_phone = Column(String(30), nullable=False)
    created_at_utc = Column(String(40), nullable=False, default=now_utc_iso)


Base.metadata.create_all(engine)

router = APIRouter()


def db() -> Session:
    return SessionLocal()


def _get_session_or_404(s: Session, session_id: str) -> SessionRow:
    row = s.get(SessionRow, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    return row


def _next_turn_index(s: Session, session_id: str) -> int:
    q = select(TurnRow.turn_index).where(TurnRow.session_id == session_id).order_by(TurnRow.turn_index.desc()).limit(1)
    last = s.execute(q).scalar_one_or_none()
    return int(last + 1) if last is not None else 1


def _load_recent_conversation(s: Session, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
    q = (
        select(TurnRow)
        .where(TurnRow.session_id == session_id)
        .order_by(TurnRow.turn_index.asc())
    )
    rows = s.execute(q).scalars().all()
    rows = rows[-limit:] if len(rows) > limit else rows

    convo: List[Dict[str, str]] = []
    for r in rows:
        if not r.text:
            continue
        role = "user" if r.speaker == "user" else "assistant"
        convo.append({"role": role, "content": r.text})
    return convo


@router.post("/session/start")
def start_session(device_info: str = Form(default="")) -> Dict[str, Any]:
    session_id = secrets.token_hex(8)
    started = now_utc_iso()

    with db() as s:
        row = SessionRow(
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
        return {"session_id": row.session_id, "ended_at_utc": row.ended_at_utc}


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

        ext = Path(audio.filename or "").suffix.lower() or ".wav"
        fname = f"{session_id}_user_{uuid.uuid4().hex}{ext}"
        out_path = AUDIO_DIR / fname

        data = audio.file.read()
        out_path.write_bytes(data)

        transcript = transcribe_audio(out_path)
        if not transcript:
            transcript = "(전사 실패)"

        context = _load_recent_conversation(s, session_id, limit=10)
        llm_eval = evaluate_transcript(transcript, context=context)

        risk_prob = float(llm_eval.get("risk_probability", 0.0))

        meta = {
            "llm_evaluation": llm_eval,
            "risk_prob": risk_prob,
        }

        row = TurnRow(
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
    if end_ms < start_ms:
        raise HTTPException(status_code=400, detail="end_ms must be >= start_ms")

    with db() as s:
        _get_session_or_404(s, session_id)

        idx = _next_turn_index(s, session_id)

        convo = _load_recent_conversation(s, session_id, limit=12)
        tts_text = make_assistant_reply(convo)
        if not tts_text:
            tts_text = "응? 다시 말해줄래?"

        fname = f"{session_id}_assistant_{uuid.uuid4().hex}.wav"
        out_path = AUDIO_DIR / fname
        synthesize_speech_to_wav(tts_text, out_path)

        row = TurnRow(
            session_id=session_id,
            turn_index=idx,
            speaker="assistant",
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            text=tts_text,
            audio_path=str(out_path),
            meta_json=None,
        )
        s.add(row)
        s.commit()

        return {
            "turn_index": idx,
            "speaker": "assistant",
            "start_ms": int(start_ms),
            "end_ms": int(end_ms),
            "tts_text": tts_text,
            "audio_path": str(out_path),
            "audio_url": f"/storage/audio/{out_path.name}",
        }


@router.get("/session/{session_id}/export/txt")
def export_txt(session_id: str) -> PlainTextResponse:
    with db() as s:
        _get_session_or_404(s, session_id)
        q = select(TurnRow).where(TurnRow.session_id == session_id).order_by(TurnRow.turn_index.asc())
        rows = s.execute(q).scalars().all()

    lines: List[str] = []
    for r in rows:
        a = r.start_ms / 1000.0
        b = r.end_ms / 1000.0
        lines.append(f"[{a:0.3f} - {b:0.3f}] {r.speaker}: {r.text or ''}")
    return PlainTextResponse("\n".join(lines))


@router.get("/session/{session_id}/export/json")
def export_json(session_id: str) -> Dict[str, Any]:
    with db() as s:
        sess = _get_session_or_404(s, session_id)
        q = select(TurnRow).where(TurnRow.session_id == session_id).order_by(TurnRow.turn_index.asc())
        rows = s.execute(q).scalars().all()

    turns: List[Dict[str, Any]] = []
    for r in rows:
        meta_obj: Optional[Dict[str, Any]] = None
        risk_prob: Optional[float] = None
        if r.meta_json:
            try:
                meta_obj = json.loads(r.meta_json)
                risk_prob = meta_obj.get("risk_prob")
            except Exception:
                meta_obj = None

        turns.append(
            {
                "turn_index": r.turn_index,
                "speaker": r.speaker,
                "start_ms": r.start_ms,
                "end_ms": r.end_ms,
                "text": r.text,
                "audio_path": r.audio_path,
                "audio_url": f"/storage/audio/{Path(r.audio_path).name}" if r.audio_path else None,
                "risk_prob": risk_prob,
                "meta_json": meta_obj,
            }
        )

    return {
        "session_id": sess.session_id,
        "started_at_utc": sess.started_at_utc,
        "ended_at_utc": sess.ended_at_utc,
        "turns": turns,
    }


@router.get("/storage/audio/{filename}")
def get_audio(filename: str):
    p = AUDIO_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(str(p), media_type="audio/wav")


@router.get("/members")
def list_members(
    search: str = "",            # 회원번호 or 이름 부분검색
    sort_by: str = "member_no",  # member_no, customer_name, guardian_name, risk, customer_phone, guardian_phone
    order: str = "asc",          # asc | desc
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    allowed = {
        "member_no": MemberRow.member_no,
        "customer_name": MemberRow.customer_name,
        "guardian_name": MemberRow.guardian_name,
        "risk": MemberRow.risk,
        "customer_phone": MemberRow.customer_phone,
        "guardian_phone": MemberRow.guardian_phone,
    }
    if sort_by not in allowed:
        raise HTTPException(status_code=400, detail="invalid sort_by")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="invalid order")

    sort_col = allowed[sort_by]
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    with db() as s:
        q = select(MemberRow)

        if search.strip():
            key = f"%{search.strip()}%"
            q = q.where(
                (MemberRow.member_no.like(key)) |
                (MemberRow.customer_name.like(key)) |
                (MemberRow.guardian_name.like(key))
            )

        q = q.order_by(sort_expr).limit(limit).offset(offset)
        rows = s.execute(q).scalars().all()

    items = []
    for r in rows:
        items.append(
            {
                "memberNo": r.member_no,
                "customerName": r.customer_name,
                "guardianName": r.guardian_name,
                "risk": r.risk,
                "customerPhone": r.customer_phone,
                "guardianPhone": r.guardian_phone,
            }
        )

    return {"items": items, "count": len(items)}


@router.post("/members/seed")
def seed_members() -> Dict[str, Any]:
    name_pool = ["김*준","박*준","이*지","최*연","정*우","강*민","조*은","윤*호","한*서","오*린"]
    guardian_pool = ["남*규","윤*희","최*수","유*진","신*아","김*경","조*람","박*원","정*인","이*솔"]
    risk_pool = [92, 86, 78, 74, 68, 65, 61, 58, 52, 49]

    members = []
    for index in range(50):
        member_no = str(12345600 + index + 1)
        customer_name = name_pool[index % len(name_pool)]
        guardian_name = guardian_pool[index % len(guardian_pool)]
        risk = risk_pool[index % len(risk_pool)]
        customer_phone = f"010-{str(1200+index).zfill(4)}-{str(5600+index).zfill(4)}"
        guardian_phone = f"010-{str(2300+index).zfill(4)}-{str(7700+index).zfill(4)}"
        members.append((member_no, customer_name, guardian_name, risk, customer_phone, guardian_phone))

    inserted = 0
    with db() as s:
        for m in members:
            if s.get(MemberRow, m[0]) is not None:
                continue
            s.add(
                MemberRow(
                    member_no=m[0],
                    customer_name=m[1],
                    guardian_name=m[2],
                    risk=m[3],
                    customer_phone=m[4],
                    guardian_phone=m[5],
                    created_at_utc=now_utc_iso(),
                )
            )
            inserted += 1
        s.commit()

    return {"inserted": inserted}


app = FastAPI()
app.include_router(router)