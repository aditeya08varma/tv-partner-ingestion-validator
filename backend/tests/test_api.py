def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_feeds(client):
    r = client.get("/api/mock/feeds")
    assert r.status_code == 200
    ids = {f["id"] for f in r.json()}
    assert "f1-monaco-replay-valid" in ids
    assert "football-cup-final-broken" in ids


def test_get_feed_not_found(client):
    r = client.get("/api/mock/feeds/does-not-exist")
    assert r.status_code == 404


def test_list_manifests(client):
    r = client.get("/api/mock/manifests")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 6
    assert all(m["manifest_url"].startswith("http://testserver/static/manifests/") for m in body)


def test_validate_metadata_endpoint_valid_mrss(client):
    feed = client.get("/api/mock/feeds/f1-monaco-replay-valid").json()
    r = client.post(
        "/api/validate/metadata",
        data={"feed_format": feed["feed_format"], "content": feed["content"]},
    )
    assert r.status_code == 200
    assert r.json()["passed"] is True


def test_validate_metadata_endpoint_broken_json(client):
    feed = client.get("/api/mock/feeds/football-cup-final-broken").json()
    r = client.post(
        "/api/validate/metadata",
        data={"feed_format": feed["feed_format"], "content": feed["content"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert len(body["issues"]) > 0


def test_validate_metadata_requires_content_or_file(client):
    r = client.post("/api/validate/metadata", data={"feed_format": "json"})
    assert r.status_code == 400


def test_validate_manifest_endpoint(client):
    manifest = next(m for m in client.get("/api/mock/manifests").json() if m["id"] == "f1-monaco-hls-valid")
    r = client.post("/api/validate/manifest", data={"manifest_url": manifest["manifest_url"]})
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is True
    assert body["segments_checked"] == 9


def test_validate_submission_combined_report(client):
    feed = client.get("/api/mock/feeds/f1-monaco-replay-valid").json()
    manifest = next(m for m in client.get("/api/mock/manifests").json() if m["id"] == "f1-monaco-hls-valid")
    r = client.post(
        "/api/validate/submission",
        data={
            "partner_name": "Apex Sports Network",
            "content_title": "F1 Monaco GP Replay",
            "feed_format": feed["feed_format"],
            "metadata_content": feed["content"],
            "manifest_url": manifest["manifest_url"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is True
    assert body["metadata_report"]["passed"] is True
    assert body["manifest_report"]["passed"] is True


def test_validate_submission_fails_when_manifest_broken(client):
    manifest = next(m for m in client.get("/api/mock/manifests").json() if m["id"] == "f1-monaco-hls-broken")
    r = client.post(
        "/api/validate/submission",
        data={"partner_name": "Apex Sports Network", "manifest_url": manifest["manifest_url"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert body["manifest_report"]["passed"] is False
