# Dependencies: fastapi, uvicorn, sqlalchemy, aiosqlite, authlib, python-jose, httpx
"""
FastAPI application entry point.
Run with: uvicorn api.main:app --reload
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api.auth import APP_SECRET_KEY, router as auth_router
from api.database import init_db
from api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    await init_db()
    yield


app = FastAPI(title="Remarkable Podcast", lifespan=lifespan)

# Session middleware (required by authlib OAuth)
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET_KEY)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.environ.get("APP_URL", "http://localhost:5173"),
        "http://localhost:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(api_router)

# Serve SPA static files (web/dist/) at root — must be last
web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="spa")
