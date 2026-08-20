"""One-off generator for mock_data/ fixtures: sample partner feeds and HLS/DASH
manifests (valid and intentionally-broken variants) used by the demo and tests.
Re-run after editing this file to regenerate the fixture tree from scratch.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app" / "mock_data"
FEEDS = ROOT / "feeds"
MANIFESTS = ROOT / "manifests"

SEGMENT_BYTES = b"\x47" + b"\x00" * 187  # one dummy MPEG-TS packet, repeated


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content)
    else:
        path.write_bytes(content)


def reset(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Metadata feeds (MRSS + JSON), F1 replay + football highlights, valid/broken
# ---------------------------------------------------------------------------

MRSS_VALID = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:epg="https://schemas.example.com/partner-epg/1.0"
     xmlns:licensing="https://schemas.example.com/partner-licensing/1.0">
  <channel>
    <title>Apex Sports Network</title>
    <item>
      <guid>f1-2026-monaco-gp-replay</guid>
      <media:title xml:lang="en-US">Formula 1: Monaco Grand Prix - Full Race Replay</media:title>
      <media:title xml:lang="fr-FR">Formule 1 : Grand Prix de Monaco - Replay complet</media:title>
      <media:thumbnail url="https://cdn.apexsports.example.com/thumbs/f1-monaco-2026.jpg"/>
      <epg:schedule>
        <epg:airing start="2026-05-24T13:00:00Z" end="2026-05-24T15:30:00Z"/>
      </epg:schedule>
      <licensing:window start="2026-05-24T00:00:00Z" end="2026-08-24T00:00:00Z" territories="US,CA,GB"/>
      <category>Motorsport</category>
    </item>
  </channel>
</rss>
"""

MRSS_BROKEN = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:epg="https://schemas.example.com/partner-epg/1.0"
     xmlns:licensing="https://schemas.example.com/partner-licensing/1.0">
  <channel>
    <title>Apex Sports Network</title>
    <item>
      <guid>f1-2026-monaco-gp-replay</guid>
      <media:title>Formula 1: Monaco Grand Prix - Full Race Replay</media:title>
      <media:thumbnail url="thumbs/f1-monaco-2026.jpg"/>
      <epg:schedule>
        <epg:airing start="2026-05-24T15:30:00Z" end="2026-05-24T13:00:00Z"/>
      </epg:schedule>
    </item>
  </channel>
</rss>
"""

JSON_VALID = """{
  "partner": "Riverside Football Network",
  "items": [
    {
      "content_id": "football-2026-cup-final-highlights",
      "titles": {
        "en-US": "Cup Final Highlights: Riverside vs Union City",
        "es-MX": "Resumen de la Final de Copa: Riverside vs Union City"
      },
      "thumbnail_url": "https://cdn.riversidefc.example.com/thumbs/cup-final-2026.jpg",
      "epg": [
        {"start": "2026-06-14T18:00:00Z", "end": "2026-06-14T18:45:00Z"}
      ],
      "licensing_window": {
        "start": "2026-06-14T00:00:00Z",
        "end": "2026-09-14T00:00:00Z",
        "territories": ["US", "MX"]
      },
      "category": "Football"
    }
  ]
}
"""

JSON_BROKEN = """{
  "partner": "Riverside Football Network",
  "items": [
    {
      "titles": {
        "en-US": "Cup Final Highlights: Riverside vs Union City"
      },
      "thumbnail_url": "cdn.riversidefc.example.com/thumbs/cup-final-2026.jpg",
      "epg": [],
      "licensing_window": {
        "start": "2026-06-14T00:00:00Z",
        "end": "2020-01-01T00:00:00Z"
      }
    }
  ]
}
"""

write(FEEDS / "f1_monaco_replay_valid.xml", MRSS_VALID)
write(FEEDS / "f1_monaco_replay_broken.xml", MRSS_BROKEN)
write(FEEDS / "football_cup_final_valid.json", JSON_VALID)
write(FEEDS / "football_cup_final_broken.json", JSON_BROKEN)


# ---------------------------------------------------------------------------
# HLS manifests, valid + broken, for two mock events
# ---------------------------------------------------------------------------

def build_hls_event(name: str, *, broken: bool) -> None:
    base = MANIFESTS / name
    reset(base)
    seg_dir = base / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    renditions = [
        ("1080p", 1920, 1080, 5_800_000, "avc1.640028,mp4a.40.2"),
        ("720p", 1280, 720, 2_800_000, "avc1.4d401f,mp4a.40.2"),
        ("480p", 854, 480, 1_400_000, "avc1.4d401e,mp4a.40.2"),
    ]
    if broken:
        renditions = [r for r in renditions if r[0] != "1080p"]  # drop the top rendition

    master_lines = ["#EXTM3U", "#EXT-X-VERSION:6"]
    if not broken:
        master_lines.append(
            '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="English",LANGUAGE="en",URI="audio_en.m3u8",DEFAULT=YES'
        )
    for label, width, height, bandwidth, codecs in renditions:
        audio_attr = ',AUDIO="aud"' if not broken else ""
        master_lines.append(
            f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height},CODECS="{codecs}"{audio_attr}'
        )
        master_lines.append(f"video_{label}.m3u8")
    write(base / "master.m3u8", "\n".join(master_lines) + "\n")

    for label, *_ in renditions:
        n_segments = 2 if (broken and label == "720p") else 3  # broken: 720p is missing its 3rd segment
        seg_lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:6",
            "#EXT-X-TARGETDURATION:6",
            "#EXT-X-PLAYLIST-TYPE:VOD",
        ]
        for i in range(3):
            seg_lines.append("#EXTINF:6.000,")
            seg_lines.append(f"segments/{label}_{i:03d}.ts")
            if i < n_segments:
                write(seg_dir / f"{label}_{i:03d}.ts", SEGMENT_BYTES)
        seg_lines.append("#EXT-X-ENDLIST")
        write(base / f"video_{label}.m3u8", "\n".join(seg_lines) + "\n")

    if not broken:
        write(
            base / "audio_en.m3u8",
            "\n".join(
                [
                    "#EXTM3U",
                    "#EXT-X-VERSION:6",
                    "#EXT-X-TARGETDURATION:6",
                    "#EXT-X-PLAYLIST-TYPE:VOD",
                    "#EXTINF:6.000,",
                    "segments/audio_000.ts",
                    "#EXT-X-ENDLIST",
                ]
            )
            + "\n",
        )
        write(seg_dir / "audio_000.ts", SEGMENT_BYTES)


build_hls_event("f1-monaco-valid", broken=False)
build_hls_event("f1-monaco-broken", broken=True)
build_hls_event("football-cup-final-valid", broken=False)
build_hls_event("football-cup-final-broken", broken=True)


# ---------------------------------------------------------------------------
# DASH (.mpd) manifests, one valid + one broken
# ---------------------------------------------------------------------------

def build_dash_event(name: str, *, broken: bool) -> None:
    base = MANIFESTS / name
    reset(base)
    seg_dir = base / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    video_reps = [
        ("v1080", 1920, 1080, 5_800_000),
        ("v720", 1280, 720, 2_800_000),
    ]
    if broken:
        video_reps = [r for r in video_reps if r[0] != "v1080"]

    def video_rep_xml(rep_id: str, width: int, height: int, bandwidth: int) -> str:
        n_segments = 1 if broken else 2  # broken: only 1 of 2 referenced segments actually exists
        seg_urls = "\n".join(
            f'          <SegmentURL media="segments/{rep_id}_{i:03d}.m4s"/>' for i in range(2)
        )
        for i in range(2):
            if i < n_segments:
                write(seg_dir / f"{rep_id}_{i:03d}.m4s", SEGMENT_BYTES)
        return f"""      <Representation id="{rep_id}" width="{width}" height="{height}" bandwidth="{bandwidth}" codecs="avc1.640028">
        <SegmentList duration="6">
{seg_urls}
        </SegmentList>
      </Representation>"""

    video_reps_xml = "\n".join(video_rep_xml(*r) for r in video_reps)

    audio_xml = ""
    if not broken:
        write(seg_dir / "a1_000.m4s", SEGMENT_BYTES)
        audio_xml = """    <AdaptationSet contentType="audio" mimeType="audio/mp4" lang="en">
      <Representation id="a1" bandwidth="128000" codecs="mp4a.40.2">
        <SegmentList duration="6">
          <SegmentURL media="segments/a1_000.m4s"/>
        </SegmentList>
      </Representation>
    </AdaptationSet>
"""

    mpd = f"""<?xml version="1.0" encoding="UTF-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT2H30M" minBufferTime="PT2S" profiles="urn:mpeg:dash:profile:isoff-main:2011">
  <Period>
    <AdaptationSet contentType="video" mimeType="video/mp4">
{video_reps_xml}
    </AdaptationSet>
{audio_xml}  </Period>
</MPD>
"""
    write(base / "manifest.mpd", mpd)


build_dash_event("f1-monaco-valid-dash", broken=False)
build_dash_event("f1-monaco-broken-dash", broken=True)

print("Fixtures generated under", ROOT)
