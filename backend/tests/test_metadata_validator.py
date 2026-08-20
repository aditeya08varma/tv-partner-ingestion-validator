from pathlib import Path

from app.validators.metadata import validate_json_feed, validate_mrss

FEEDS = Path(__file__).resolve().parent.parent / "app" / "mock_data" / "feeds"


def test_valid_mrss_passes():
    report = validate_mrss((FEEDS / "f1_monaco_replay_valid.xml").read_bytes())
    assert report.passed
    assert report.items_checked == 1
    assert report.issues == []


def test_broken_mrss_fails_with_line_numbers():
    report = validate_mrss((FEEDS / "f1_monaco_replay_broken.xml").read_bytes())
    assert not report.passed
    errors = [i for i in report.issues if i.severity == "error"]
    assert len(errors) >= 3
    assert all(i.line is not None for i in report.issues)
    assert any("licensing" in i.field for i in errors)


def test_malformed_xml_reports_syntax_error():
    report = validate_mrss(b"<rss><channel><item></rss>")
    assert not report.passed
    assert "Invalid XML" in report.issues[0].message


def test_valid_json_feed_passes():
    report = validate_json_feed((FEEDS / "football_cup_final_valid.json").read_bytes())
    assert report.passed
    assert report.items_checked == 1


def test_broken_json_feed_fails():
    report = validate_json_feed((FEEDS / "football_cup_final_broken.json").read_bytes())
    assert not report.passed
    fields = {i.field for i in report.issues}
    assert "$.items[0].content_id" in fields
    assert "$.items[0].epg" in fields


def test_malformed_json_reports_syntax_error():
    report = validate_json_feed(b"{not valid json")
    assert not report.passed
    assert "Invalid JSON" in report.issues[0].message


def test_expired_licensing_window_is_warning_not_error():
    raw = b"""
    {"items": [{
        "content_id": "x",
        "titles": {"en-US": "A", "es-MX": "B"},
        "thumbnail_url": "https://example.com/t.jpg",
        "epg": [{"start": "2020-01-01T00:00:00Z", "end": "2020-01-01T01:00:00Z"}],
        "licensing_window": {"start": "2019-01-01T00:00:00Z", "end": "2020-01-01T00:00:00Z", "territories": ["US"]}
    }]}
    """
    report = validate_json_feed(raw)
    assert report.passed
    assert any("expired" in i.message for i in report.issues)
