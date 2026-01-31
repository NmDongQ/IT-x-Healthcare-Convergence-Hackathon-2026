from __future__ import annotations

from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base

class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(32), primary_key=True)
    device_info = Column(String(200), nullable=True)
    started_at_utc = Column(String(40), nullable=False)
    ended_at_utc = Column(String(40), nullable=True)
    
    # [NEW] 분석 결과 영구 저장용 컬럼 (JSON 문자열 저장)
    final_report = Column(Text, nullable=True)

    turns = relationship("Turn", back_populates="session", cascade="all, delete-orphan")


class Turn(Base):
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

    session = relationship("Session", back_populates="turns")


class Member(Base):
    __tablename__ = "members"

    member_no = Column(String(32), primary_key=True)
    customer_name = Column(String(50), nullable=False)
    guardian_name = Column(String(50), nullable=False)
    risk = Column(Integer, nullable=False)  # 0~100
    customer_phone = Column(String(30), nullable=False)
    guardian_phone = Column(String(30), nullable=False)
    created_at_utc = Column(String(40), nullable=False)