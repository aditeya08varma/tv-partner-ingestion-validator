from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/mock", tags=["mock-fixtures"])

MOCK_DATA = Path(__file__).resolve().parent.parent / "mock_data"
FEEDS_DIR = MOCK_DATA / "feeds"

FEED_FIXTURES = [
    {
        "id": "f1-monaco-replay-valid",
        "label": "F1: Monaco GP Replay (valid MRSS)",
        "sport": "Formula 1",
        "feed_format": "mrss",
        "expected_valid": True,
        "file": "f1_monaco_replay_valid.xml",
    },
    {
        "id": "f1-monaco-replay-broken",
        "label": "F1: Monaco GP Replay (broken MRSS)",
        "sport": "Formula 1",
        "feed_format": "mrss",
        "expected_valid": False,
        "file": "f1_monaco_replay_broken.xml",
    },
    {
        "id": "football-cup-final-valid",
        "label": "Football: Cup Final Highlights (valid JSON)",
        "sport": "Football",
        "feed_format": "json",
        "expected_valid": True,
        "file": "football_cup_final_valid.json",
    },
    {
        "id": "football-cup-final-broken",
        "label": "Football: Cup Final Highlights (broken JSON)",
        "sport": "Football",
        "feed_format": "json",
        "expected_valid": False,
        "file": "football_cup_final_broken.json",
    },
]

MANIFEST_FIXTURES = [
    {
        "id": "f1-monaco-hls-valid",
        "label": "F1: Monaco GP Replay (valid HLS)",
        "sport": "Formula 1",
        "manifest_type": "hls",
        "expected_valid": True,
        "path": "manifests/f1-monaco-valid/master.m3u8",
    },
    {
        "id": "f1-monaco-hls-broken",
        "label": "F1: Monaco GP Replay (broken HLS)",
        "sport": "Formula 1",
        "manifest_type": "hls",
        "expected_valid": False,
        "path": "manifests/f1-monaco-broken/master.m3u8",
    },
    {
        "id": "football-cup-final-hls-valid",
        "label": "Football: Cup Final Highlights (valid HLS)",
        "sport": "Football",
        "manifest_type": "hls",
        "expected_valid": True,
        "path": "manifests/football-cup-final-valid/master.m3u8",
    },
    {
        "id": "football-cup-final-hls-broken",
        "label": "Football: Cup Final Highlights (broken HLS)",
        "sport": "Football",
        "manifest_type": "hls",
        "expected_valid": False,
        "path": "manifests/football-cup-final-broken/master.m3u8",
    },
    {
        "id": "f1-monaco-dash-valid",
        "label": "F1: Monaco GP Replay (valid DASH)",
        "sport": "Formula 1",
        "manifest_type": "dash",
        "expected_valid": True,
        "path": "manifests/f1-monaco-valid-dash/manifest.mpd",
    },
    {
        "id": "f1-monaco-dash-broken",
        "label": "F1: Monaco GP Replay (broken DASH)",
        "sport": "Formula 1",
        "manifest_type": "dash",
        "expected_valid": False,
        "path": "manifests/f1-monaco-broken-dash/manifest.mpd",
    },
]


@router.get("/feeds")
def list_feeds():
    return [{k: v for k, v in f.items() if k != "file"} for f in FEED_FIXTURES]


@router.get("/feeds/{feed_id}")
def get_feed(feed_id: str):
    fixture = next((f for f in FEED_FIXTURES if f["id"] == feed_id), None)
    if fixture is None:
        raise HTTPException(status_code=404, detail=f"Unknown fixture id: {feed_id}")
    content = (FEEDS_DIR / fixture["file"]).read_text()
    return {**{k: v for k, v in fixture.items() if k != "file"}, "content": content}


@router.get("/manifests")
def list_manifests(request: Request):
    base = str(request.base_url).rstrip("/")
    return [
        {**{k: v for k, v in m.items() if k != "path"}, "manifest_url": f"{base}/static/{m['path']}"}
        for m in MANIFEST_FIXTURES
    ]
