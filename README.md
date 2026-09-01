# Media Partner Ingestion Validator

A self-service tool that simulates how a TV/media partner (e.g. a sports network)
submits schedule metadata and media manifests for ingestion onto a video platform,
and validates that submission against platform standards **before** it goes live.

Built to mirror the technical integration work of a **TV Partner Engineer**: partner
self-service tooling, XML/HTTP troubleshooting, and automated pre-flight checks that
reduce manual back-and-forth between partners and operations.

Mock content: Formula 1 race replays and football match highlights, standing in for
real sports broadcast partner submissions.

## In plain English

Think of a video platform as a giant library of TV shows. Before a channel's
show can go on the shelf, someone has to check two things: **is the label
right** (title, thumbnail, air time, licensing dates), and **does the video
actually play** (right resolutions, has sound, no missing pieces). Normally a
person checks this by hand, every time, for every show — slow and error-prone.

This project is a robot that does both checks in under a second and tells you
*exactly* what's wrong — "line 42 is missing a title" or "the 1080p version
is missing" — instead of just failing silently. Press one button, get either
a ✅ **pass** or a ❌ **fail with the precise fix needed**.

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

## Why this tech stack

| Layer | Choice | Why this, specifically |
|---|---|---|
| **Backend API** | Python + FastAPI | Async-native, so segment-URL probing (many concurrent HTTP HEAD requests per manifest) doesn't block the event loop. Pydantic models give the validators a typed, self-documenting output contract, and FastAPI turns that straight into OpenAPI docs (`/docs`) — useful for a partner-facing API that others will integrate against. |
| **XML parsing** | `lxml` | The stdlib `xml.etree` can't report source line numbers. Partner-facing error messages like *"Invalid XML tag on line 42"* require it — `lxml` exposes `.sourceline` on every element, which is what makes the metadata validator's errors locatable instead of just "somewhere in your file." |
| **HLS parsing** | `m3u8` | Purpose-built for exactly this: parsing master/variant playlists, `EXT-X-STREAM-INF` (bandwidth/resolution/codecs) and `EXT-X-MEDIA` (alternate audio/subtitle renditions) without hand-rolling an M3U8 grammar. |
| **DASH parsing** | `lxml` (direct MPD XML) | No mature, lightweight pure-Python DASH manifest library exists the way `m3u8` covers HLS, so `.mpd` (`AdaptationSet`/`Representation`/`SegmentList`) is parsed directly against the MPEG-DASH XML namespace — small enough surface area that a dependency wasn't worth adding. |
| **Segment probing** | `httpx.AsyncClient` | Async HEAD requests (falling back to GET on 405) across all sampled segments concurrently, bounded by a semaphore — checking a full rendition ladder's segments is a fan-out I/O problem, not a CPU one. |
| **Frontend** | React + TypeScript | The dashboard's entire value is structured state: three independent report shapes (metadata / manifest / combined) that have to render consistently and stay in sync with what the partner just submitted. TypeScript interfaces mirroring the Pydantic models catch response-shape drift at compile time instead of in the browser console. |
| **Build tooling** | Vite | Fast dev-server iteration with an API proxy to the FastAPI backend, avoiding CORS friction during development while `app/main.py` still runs actual CORS middleware for the deployed/Docker case. |
| **Containerization** | Docker + Docker Compose | Two independently deployable services (API, dashboard) that a real partner-integrations team would run and version separately; Compose wires them into one command for local/demo use. |
| **Testing** | pytest + pytest-asyncio, in-process ASGI transport | Manifest validation makes real HTTP calls (to probe segments) — instead of mocking that away, tests route those calls through `httpx.ASGITransport` back into the same FastAPI app in-process, so the 404-detection path is exercised for real, with zero live server and zero network flakiness. |

See [`docs/PROJECT_WRITEUP.md`](docs/PROJECT_WRITEUP.md) for the full build
story — architecture and validation-flow diagrams, real bugs found and fixed,
results from testing against live public HLS/DASH streams, and verified
metrics.

