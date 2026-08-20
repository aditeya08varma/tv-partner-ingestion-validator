from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import mock, validate

MOCK_DATA_DIR = Path(__file__).resolve().parent / "mock_data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="Media Partner Ingestion Validator",
    description="Validates partner schedule metadata (MRSS/JSON) and HLS/DASH media manifests before go-live.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=MOCK_DATA_DIR), name="static")

app.include_router(validate.router)
app.include_router(mock.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
