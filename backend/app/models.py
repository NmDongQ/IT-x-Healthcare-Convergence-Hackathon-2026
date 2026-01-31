# backend/app/models.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 선택: 기기/앱 정보
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    turns: Mapped[list["Turn"]] = relationship(
        "Turn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Turn.turn_index",
    )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)

    speaker: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"

    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[str | None] = mapped_column(Text, nullable=True)      # user 전사 or assistant 발화문
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True) # 서버에 저장한 파일 경로

    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True) # 필요 시 JSON string

    session: Mapped["Session"] = relationship("Session", back_populates="turns")