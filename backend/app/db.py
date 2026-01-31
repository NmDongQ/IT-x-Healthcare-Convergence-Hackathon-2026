from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 경로를 backend/storage/app.sqlite3 로 명확하게 지정
ROOT_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = ROOT_DIR / "storage"
DB_PATH = STORAGE_DIR / "app.sqlite3"

# 저장소 디렉토리 생성
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# SQLite URL
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},  # SQLite & FastAPI 필수 설정
    future=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()