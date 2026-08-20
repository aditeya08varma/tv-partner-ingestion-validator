"""Fetches and validates HLS (.m3u8) and DASH (.mpd) media manifests.

Checks that required video renditions and audio tracks are present, then
probes a sample of segment URLs so broken renditions surface before a
partner goes live, mirroring the "does this actually play" checks a TV
Partner Engineer runs during onboarding.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urljoin, urlparse

import httpx
import m3u8
from lxml import etree

from app.models import (
    AudioTrackInfo,
    Issue,
    ManifestReport,
    RenditionInfo,
    SegmentCheck,
    Severity,
)

REQUIRED_HEIGHTS = (1080, 720)
SEGMENTS_SAMPLED_PER_RENDITION = 3
MAX_CONCURRENT_SEGMENT_CHECKS = 8


def _label_for_height(height: int | None) -> str:
    return f"{height}p" if height else "unknown"


async def _check_segment(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore) -> SegmentCheck:
    async with sem:
        try:
            resp = await client.head(url, timeout=8.0, follow_redirects=True)
            if resp.status_code == 405:
                resp = await client.get(url, timeout=8.0, follow_redirects=True)
            ok = resp.status_code < 400
            return SegmentCheck(uri=url, ok=ok, status_code=resp.status_code)
        except httpx.HTTPError as exc:
            return SegmentCheck(uri=url, ok=False, error=str(exc))


async def _check_segments(client: httpx.AsyncClient, urls: list[str]) -> list[SegmentCheck]:
    sem = asyncio.Semaphore(MAX_CONCURRENT_SEGMENT_CHECKS)
    results = await asyncio.gather(*[_check_segment(client, u, sem) for u in urls])
    return list(results)


async def validate_hls(
    manifest_url: str,
    client: httpx.AsyncClient,
    required_heights: tuple[int, ...] = REQUIRED_HEIGHTS,
) -> ManifestReport:
    issues: list[Issue] = []

    try:
        resp = await client.get(manifest_url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return ManifestReport(
            passed=False,
            manifest_type="hls",
            manifest_url=manifest_url,
            renditions=[],
            audio_tracks=[],
            missing_required_renditions=[f"{h}p" for h in required_heights],
            segments_checked=0,
            broken_segments=[],
            issues=[Issue(severity=Severity.ERROR, field="manifest_url", message=f"Could not fetch manifest: {exc}")],
        )

    playlist = m3u8.loads(resp.text, uri=manifest_url)

    if not playlist.is_variant:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                field="manifest",
                message="Manifest is a media playlist, not a master playlist — no rendition ladder to validate.",
            )
        )
        renditions: list[RenditionInfo] = []
    else:
        renditions = []
        for p in playlist.playlists:
            width = height = None
            if p.stream_info and p.stream_info.resolution:
                width, height = p.stream_info.resolution
            renditions.append(
                RenditionInfo(
                    resolution_label=_label_for_height(height),
                    width=width,
                    height=height,
                    bandwidth=p.stream_info.bandwidth if p.stream_info else None,
                    codecs=p.stream_info.codecs if p.stream_info else None,
                    uri=urljoin(manifest_url, p.uri),
                )
            )

    present_heights = {r.height for r in renditions if r.height}
    missing = [_label_for_height(h) for h in required_heights if h not in present_heights]
    for label in missing:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                field="manifest#EXT-X-STREAM-INF",
                message=f"Missing {label} rendition in manifest.",
            )
        )

    audio_tracks: list[AudioTrackInfo] = []
    for media in playlist.media:
        if (media.type or "").upper() == "AUDIO":
            audio_tracks.append(
                AudioTrackInfo(
                    group_id=media.group_id or "",
                    name=media.name or "",
                    language=media.language,
                    uri=urljoin(manifest_url, media.uri) if media.uri else None,
                )
            )
    if not audio_tracks:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                field="manifest#EXT-X-MEDIA",
                message="No AUDIO renditions (EXT-X-MEDIA TYPE=AUDIO) found in manifest.",
            )
        )

    segment_urls: list[str] = []
    for r in renditions:
        try:
            variant_resp = await client.get(r.uri, timeout=10.0, follow_redirects=True)
            variant_resp.raise_for_status()
        except httpx.HTTPError as exc:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"rendition[{r.resolution_label}]",
                    message=f"Could not fetch variant playlist {r.uri}: {exc}",
                )
            )
            continue
        variant = m3u8.loads(variant_resp.text, uri=r.uri)
        for seg in variant.segments[:SEGMENTS_SAMPLED_PER_RENDITION]:
            segment_urls.append(urljoin(r.uri, seg.uri))

    broken_segments: list[SegmentCheck] = []
    if segment_urls:
        checks = await _check_segments(client, segment_urls)
        broken_segments = [c for c in checks if not c.ok]
        for c in broken_segments:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field="segment",
                    message=f"Segment returned {c.status_code or c.error}: {c.uri}",
                )
            )

    passed = not any(i.severity == Severity.ERROR for i in issues)
    return ManifestReport(
        passed=passed,
        manifest_type="hls",
        manifest_url=manifest_url,
        renditions=renditions,
        audio_tracks=audio_tracks,
        missing_required_renditions=missing,
        segments_checked=len(segment_urls),
        broken_segments=broken_segments,
        issues=issues,
    )


_MPD_NS = {"m": "urn:mpeg:dash:schema:mpd:2011"}


async def validate_dash(
    manifest_url: str,
    client: httpx.AsyncClient,
    required_heights: tuple[int, ...] = REQUIRED_HEIGHTS,
) -> ManifestReport:
    issues: list[Issue] = []

    try:
        resp = await client.get(manifest_url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return ManifestReport(
            passed=False,
            manifest_type="dash",
            manifest_url=manifest_url,
            renditions=[],
            audio_tracks=[],
            missing_required_renditions=[f"{h}p" for h in required_heights],
            segments_checked=0,
            broken_segments=[],
            issues=[Issue(severity=Severity.ERROR, field="manifest_url", message=f"Could not fetch manifest: {exc}")],
        )

    try:
        root = etree.fromstring(resp.content)
    except etree.XMLSyntaxError as exc:
        return ManifestReport(
            passed=False,
            manifest_type="dash",
            manifest_url=manifest_url,
            renditions=[],
            audio_tracks=[],
            missing_required_renditions=[f"{h}p" for h in required_heights],
            segments_checked=0,
            broken_segments=[],
            issues=[Issue(severity=Severity.ERROR, field="manifest", message=f"Invalid MPD XML: {exc.msg}", line=exc.lineno)],
        )

    renditions: list[RenditionInfo] = []
    audio_tracks: list[AudioTrackInfo] = []
    segment_urls: list[str] = []

    for adaptation_set in root.findall(".//m:AdaptationSet", namespaces=_MPD_NS):
        content_type = adaptation_set.get("contentType") or adaptation_set.get("mimeType", "")
        is_audio = "audio" in content_type.lower()

        for rep in adaptation_set.findall("m:Representation", namespaces=_MPD_NS):
            rep_id = rep.get("id", "")
            width = int(rep.get("width")) if rep.get("width") else None
            height = int(rep.get("height")) if rep.get("height") else None
            bandwidth = int(rep.get("bandwidth")) if rep.get("bandwidth") else None
            codecs = rep.get("codecs")

            if is_audio:
                audio_tracks.append(
                    AudioTrackInfo(group_id=rep_id, name=rep_id, language=adaptation_set.get("lang"), uri=None)
                )
            else:
                renditions.append(
                    RenditionInfo(
                        resolution_label=_label_for_height(height),
                        width=width,
                        height=height,
                        bandwidth=bandwidth,
                        codecs=codecs,
                        uri=manifest_url,
                    )
                )

            seg_list = rep.find("m:SegmentList", namespaces=_MPD_NS)
            if seg_list is not None:
                for seg_url in seg_list.findall("m:SegmentURL", namespaces=_MPD_NS)[:SEGMENTS_SAMPLED_PER_RENDITION]:
                    media = seg_url.get("media")
                    if media:
                        segment_urls.append(urljoin(manifest_url, media))

    present_heights = {r.height for r in renditions if r.height}
    missing = [_label_for_height(h) for h in required_heights if h not in present_heights]
    for label in missing:
        issues.append(
            Issue(severity=Severity.ERROR, field="MPD/AdaptationSet/Representation", message=f"Missing {label} rendition in manifest.")
        )

    if not audio_tracks:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                field="MPD/AdaptationSet[@contentType='audio']",
                message="No audio AdaptationSet found in manifest.",
            )
        )

    broken_segments: list[SegmentCheck] = []
    if segment_urls:
        checks = await _check_segments(client, segment_urls)
        broken_segments = [c for c in checks if not c.ok]
        for c in broken_segments:
            issues.append(
                Issue(severity=Severity.ERROR, field="segment", message=f"Segment returned {c.status_code or c.error}: {c.uri}")
            )

    passed = not any(i.severity == Severity.ERROR for i in issues)
    return ManifestReport(
        passed=passed,
        manifest_type="dash",
        manifest_url=manifest_url,
        renditions=renditions,
        audio_tracks=audio_tracks,
        missing_required_renditions=missing,
        segments_checked=len(segment_urls),
        broken_segments=broken_segments,
        issues=issues,
    )


async def validate_manifest(manifest_url: str, client: httpx.AsyncClient) -> ManifestReport:
    path = urlparse(manifest_url).path.lower()
    if path.endswith(".mpd"):
        return await validate_dash(manifest_url, client)
    return await validate_hls(manifest_url, client)
