# Media Partner Ingestion Validator

A self-service tool that simulates how a TV/media partner (e.g. a sports network)
submits schedule metadata and media manifests for ingestion onto a video platform,
and validates that submission against platform standards **before** it goes live.

Built to mirror the technical integration work of a **TV Partner Engineer**: partner
self-service tooling, XML/HTTP troubleshooting, and automated pre-flight checks that
reduce manual back-and-forth between partners and operations.

Mock content: Formula 1 race replays and football match highlights, standing in for
real sports broadcast partner submissions.

## What it checks

1. **Schedule metadata** (MRSS/XML or JSON feed) — localized titles, thumbnail URLs,
   EPG airing schedule, and licensing window, with field-level and line-level errors.
2. **Media manifest** (HLS `.m3u8` or DASH `.mpd`) — required video renditions
   (1080p/720p), audio tracks, and a live HTTP probe of segment URLs to catch 404s
   before a partner's stream goes live.
3. **Combined submission report** — both checks run together into a single
   pass/fail go-live decision.

## Quick start

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_fixtures.py   # generates mock F1/football feeds + manifests
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API docs (Swagger UI) at `http://localhost:8000/docs`.

Run tests:

```bash
cd backend && source .venv/bin/activate && python -m pytest -v
```

### Docker

```bash
docker compose up --build
```

Backend on `:8000`, frontend on `:4173`.

## Architecture

```
frontend/  React + TypeScript dashboard — submit feeds/manifests, view structured
           pass/fail reports with inline error logs.
backend/
  app/validators/metadata.py   MRSS (lxml, with source line numbers) + JSON validation
  app/validators/manifest.py   HLS (m3u8 lib) + DASH (lxml) parsing, async segment
                                probing via httpx
  app/routers/                 /api/validate/*, /api/mock/* (fixture feeds/manifests)
  app/mock_data/                generated F1 + football fixtures (valid & broken)
  tests/                        22 tests, run in-process against the ASGI app
                                (no live server needed — see tests/conftest.py)
```

See [`docs/PROJECT_WRITEUP.md`](docs/PROJECT_WRITEUP.md) for motivation, tech
stack rationale, metrics, and resume-ready impact bullets.
