import pytest

from app.validators.manifest import validate_manifest


@pytest.mark.asyncio
async def test_valid_hls_manifest_passes(client):
    http_client = client.app.state.http_client
    url = "http://testserver/static/manifests/f1-monaco-valid/master.m3u8"
    report = await validate_manifest(url, http_client)
    assert report.passed
    assert report.manifest_type == "hls"
    assert {r.resolution_label for r in report.renditions} == {"1080p", "720p", "480p"}
    assert len(report.audio_tracks) == 1
    assert report.missing_required_renditions == []
    assert report.broken_segments == []


@pytest.mark.asyncio
async def test_broken_hls_manifest_reports_missing_rendition_and_404(client):
    http_client = client.app.state.http_client
    url = "http://testserver/static/manifests/f1-monaco-broken/master.m3u8"
    report = await validate_manifest(url, http_client)
    assert not report.passed
    assert report.missing_required_renditions == ["1080p"]
    assert any("Missing 1080p rendition" in i.message for i in report.issues)
    assert any(i.status_code == 404 for i in report.broken_segments) if report.broken_segments else True
    assert len(report.broken_segments) == 1
    assert report.audio_tracks == []


@pytest.mark.asyncio
async def test_valid_dash_manifest_passes(client):
    http_client = client.app.state.http_client
    url = "http://testserver/static/manifests/f1-monaco-valid-dash/manifest.mpd"
    report = await validate_manifest(url, http_client)
    assert report.passed
    assert report.manifest_type == "dash"
    assert {r.resolution_label for r in report.renditions} == {"1080p", "720p"}
    assert len(report.audio_tracks) == 1


@pytest.mark.asyncio
async def test_broken_dash_manifest_fails(client):
    http_client = client.app.state.http_client
    url = "http://testserver/static/manifests/f1-monaco-broken-dash/manifest.mpd"
    report = await validate_manifest(url, http_client)
    assert not report.passed
    assert "1080p" in report.missing_required_renditions
    assert report.audio_tracks == []
    assert len(report.broken_segments) == 1


@pytest.mark.asyncio
async def test_unreachable_manifest_url_reports_fetch_error(client):
    http_client = client.app.state.http_client
    url = "http://testserver/static/manifests/does-not-exist/master.m3u8"
    report = await validate_manifest(url, http_client)
    assert not report.passed
    assert "Could not fetch manifest" in report.issues[0].message
