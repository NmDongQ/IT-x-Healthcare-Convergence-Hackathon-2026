from __future__ import annotations

from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
load_dotenv()


from .db import engine
from .models import Base
from .api import router

app = FastAPI(title="Naduri Backend")

Base.metadata.create_all(bind=engine)

# RN 개발용 CORS(나중에 도메인 제한)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

app.mount(
    "/",
    StaticFiles(directory="../frontend", html=True),
    name="frontend",
)