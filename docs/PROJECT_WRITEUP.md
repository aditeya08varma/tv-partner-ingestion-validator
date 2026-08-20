# Media Partner Ingestion Validator — Project Writeup

## Motivation

Media platforms that carry third-party TV/sports content (YouTube Primetime
Channels, cable-replacement services, etc.) have to onboard partners who each
submit schedule metadata and video manifests in slightly different states of
correctness. In practice, a large share of onboarding friction is not
exotic — it's the same handful of problems every time: a missing localized
title, a thumbnail URL that's relative instead of absolute, a licensing
window that expired before anyone noticed, an HLS ladder missing its 1080p
rendition, or a video segment that 404s the moment a partner's CDN
reorganizes storage.

Today that friction is usually resolved by a human — a partner engineer —
manually inspecting an XML feed or pinging manifest URLs by hand, then
emailing the partner back with what's wrong. That doesn't scale past a
handful of partners, and it makes every partner's first submission a slow,
back-and-forth process instead of a fast, self-service one.

This project is a working simulation of the self-service pre-flight tool
that would remove most of that manual work: partners (or the engineers
supporting them) submit a feed and a manifest URL, and get back a structured,
actionable pass/fail report — the same categories of checks a TV Partner
Engineer runs by hand today, automated and instant. It directly mirrors the
responsibilities in YouTube's TV Partner Engineer role: technical partner
integrations, self-service tooling, and troubleshooting XML/HTTP issues in a
media/TV context.

## Tech stack — and why

| Layer | Choice | Why this, specifically |
|---|---|---|
| **Backend API** | Python + FastAPI | Async-native, so segment-URL probing (many concurrent HTTP HEAD requests per manifest) doesn't block the event loop. Pydantic models give the validators a typed, self-documenting output contract, and FastAPI turns that straight into OpenAPI docs (`/docs`) — useful for a partner-facing API that others will integrate against. |
| **XML parsing** | `lxml` | The stdlib `xml.etree` can't report source line numbers. Partner-facing error messages like *"Invalid XML tag on line 42"* require it — `lxml` exposes `.sourceline` on every element, which is what makes the metadata validator's errors locatable instead of just "somewhere in your file." |
| **HLS parsing** | `m3u8` | Purpose-built for exactly this: parsing master/variant playlists, `EXT-X-STREAM-INF` (bandwidth/resolution/codecs) and `EXT-X-MEDIA` (alternate audio/subtitle renditions) without hand-rolling an M3U8 grammar. |
| **DASH parsing** | `lxml` (direct MPD XML) | No mature, lightweight pure-Python DASH manifest library exists the way `m3u8` covers HLS, so `.mpd` (`AdaptationSet`/`Representation`/`SegmentList`) is parsed directly against the MPEG-DASH XML namespace — small enough surface area that a dependency wasn't worth adding. |
| **Segment probing** | `httpx.AsyncClient` | Async HEAD requests (falling back to GET on 405) across all sampled segments concurrently, bounded by a semaphore — checking a full rendition ladder's segments is a fan-out I/O problem, not a CPU one. |
| **Frontend** | React + TypeScript | The dashboard's entire value is structured state: three independent report shapes (metadata / manifest / combined) that have to render consistently and stay in sync with what the partner just submitted. TypeScript interfaces mirroring the Pydantic models catch response-shape drift at compile time instead of in the browser console. |
| **Build tooling** | Vite | Fast dev-server iteration with an API proxy to the FastAPI backend, avoiding CORS friction during development while `app/main.py` still runs actual CORS middleware for the deployed/Docker case. |
| **Containerization** | Docker + Docker Compose | Two independently deployable services (API, dashboard) that a real partner-integrations team would run and version separately; Compose wires them into one command for local/demo use, matching how the "testing suite runs consistently across environments" requirement plays out in practice. |
| **Testing** | pytest + pytest-asyncio, in-process ASGI transport | Manifest validation makes real HTTP calls (to probe segments) — instead of mocking that away, tests route those calls through `httpx.ASGITransport` back into the same FastAPI app in-process. That means the 404-detection path is exercised for real (an actually-missing fixture segment actually returns a 404) with zero live server and zero network flakiness. |

## How it solves the problem

The tool is organized around the two things a partner actually uploads:

1. **`app/validators/metadata.py`** parses an MRSS/XML or JSON feed and checks,
   per item: a content ID exists, at least one (ideally 2+) localized title is
   present and non-empty, the thumbnail URL is absolute http(s), an EPG
   schedule has valid, correctly-ordered start/end times, and a licensing
   window exists with valid, non-inverted dates and declared territories
   (warning, not blocking, if the window has already expired). XML errors
   report a source line number; JSON errors report a `$.items[n].field`
   JSONPath-style locator — both are exact enough to fix without re-reading
   the whole file.

2. **`app/validators/manifest.py`** fetches a manifest URL, auto-detects
   HLS vs. DASH by extension, and for HLS parses the master playlist's
   variant streams (checking for required 1080p/720p renditions and at least
   one `AUDIO` rendition group), then fetches each variant's child playlist
   and samples its segments for a live HTTP existence check. DASH follows the
   same shape against `AdaptationSet`/`Representation`/`SegmentList`. Every
   finding — a missing rendition, a missing audio track, a 404'd segment — is
   emitted as a structured `Issue` with severity, a field locator, and a
   human-readable message.

3. **`app/routers/validate.py`** exposes three endpoints: validate metadata
   alone, validate a manifest alone, or validate a full submission (both
   together) with one combined pass/fail — mirroring how a real partner
   onboarding checklist gates go-live on *both* metadata and media being
   correct, not either in isolation.

4. **The React dashboard** lets a user load one of the built-in F1/football
   sample fixtures (both a clean version and an intentionally-broken version
   of each), paste or edit content, and see the same structured report a
   partner would see in production — color-coded severity, per-issue field
   locators and line numbers, a rendition table, and a final go-live verdict.

5. **Fixtures are real, not simulated in code.** `scripts/generate_fixtures.py`
   materializes actual `.m3u8`/`.mpd` files and dummy segment files on disk,
   served by the backend's own `StaticFiles` mount. The "broken" manifest
   fixtures are broken for real — a segment file is simply not written to
   disk — so the demo's 404 detection is a real HTTP 404, not a mocked one.

## Metrics

- **1,074** lines of backend Python (validators, routers, models, config)
- **461** lines of frontend TypeScript/TSX
- **22/22** tests passing, covering both validators and all API endpoints,
  including the real-HTTP 404-detection path
- **51** distinct validation rules across the metadata and manifest validators
  (40 metadata checks: title/thumbnail/EPG/licensing; 11 manifest checks:
  renditions/audio/segments, across both HLS and DASH)
- **10** mock fixtures (4 metadata feeds, 6 manifests across HLS/DASH),
  each with a deliberately valid and a deliberately broken variant
- **149.98 kB** production frontend bundle (48.06 kB gzipped)
- **3** independently runnable/deployable units (FastAPI backend, React
  frontend, Docker Compose wiring both) — 0 required external services;
  the entire demo runs fully offline against its own fixtures

## Resume-ready impact bullets

- Architected a self-service media ingestion validator in Python/FastAPI
  that automates compliance checks — localized titles, EPG schedules,
  licensing windows, HLS/DASH rendition ladders — across 51 validation
  rules, replacing manual partner-feed review with instant, line-level
  structured error reports.
- Built an async HTTP segment-probing pipeline (`httpx` + `m3u8`/`lxml`)
  that concurrently verifies required video bitrates, audio tracks, and
  live segment availability across HLS and DASH manifests, surfacing broken
  renditions (e.g. "Missing 1080p rendition") before partner content reaches
  go-live.
- Engineered a React/TypeScript partner dashboard that turns raw validation
  output into an actionable pass/fail report with per-field error locators
  and source line numbers, cutting the loop between "partner submits" and
  "partner knows exactly what to fix" from a manual review cycle to
  sub-second, self-service feedback.
- Containerized the full stack (Docker + Docker Compose) with an
  in-process, network-free test suite (pytest + ASGI transport, 22 tests)
  that exercises real HTTP 404-detection logic without a live server,
  ensuring the ingestion pipeline is verifiably correct pre-deployment.
