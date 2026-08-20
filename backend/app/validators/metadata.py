"""Validates partner-submitted schedule metadata feeds (MRSS/XML or JSON).

Mirrors the kind of feed a TV/media partner pushes for EPG + licensing
ingestion: localized titles, thumbnails, an EPG airing schedule, and a
licensing window. Every failure is reported with a field locator (and a
source line number for XML) so a partner can self-service the fix.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

from lxml import etree

from app.models import FeedFormat, Issue, MetadataReport, Severity

REQUIRED_MRSS_NAMESPACES = {
    "media": "http://search.yahoo.com/mrss/",
    "epg": "https://schemas.example.com/partner-epg/1.0",
    "licensing": "https://schemas.example.com/partner-licensing/1.0",
}


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def validate_mrss(xml_bytes: bytes) -> MetadataReport:
    issues: list[Issue] = []
    parser = etree.XMLParser(recover=False)

    try:
        tree = etree.parse(BytesIO(xml_bytes), parser)
    except etree.XMLSyntaxError as exc:
        return MetadataReport(
            passed=False,
            feed_format=FeedFormat.MRSS,
            items_checked=0,
            issues=[
                Issue(
                    severity=Severity.ERROR,
                    field="document",
                    message=f"Invalid XML: {exc.msg}",
                    line=exc.lineno,
                )
            ],
        )

    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                field="rss/channel",
                message="Missing required <channel> element under <rss>.",
                line=root.sourceline,
            )
        )
        return MetadataReport(passed=False, feed_format=FeedFormat.MRSS, items_checked=0, issues=issues)

    items = channel.findall("item")
    if not items:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                field="rss/channel",
                message="Feed contains no <item> entries; nothing to ingest.",
                line=channel.sourceline,
            )
        )

    ns = REQUIRED_MRSS_NAMESPACES

    for idx, item in enumerate(items):
        locator = f"item[{idx}]"
        guid = item.find("guid")
        if guid is None or not (guid.text or "").strip():
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"{locator}/guid",
                    message="Missing <guid> content id — required to key this asset in the catalog.",
                    line=item.sourceline,
                )
            )

        titles = item.findall("media:title", namespaces=ns)
        if not titles:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"{locator}/media:title",
                    message="No localized <media:title> elements found.",
                    line=item.sourceline,
                )
            )
        else:
            seen_locales = set()
            for t in titles:
                lang = t.get("{http://www.w3.org/XML/1998/namespace}lang")
                if not lang:
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            field=f"{locator}/media:title",
                            message="<media:title> is missing an xml:lang attribute — titles must be localized.",
                            line=t.sourceline,
                        )
                    )
                elif lang in seen_locales:
                    issues.append(
                        Issue(
                            severity=Severity.WARNING,
                            field=f"{locator}/media:title[@xml:lang='{lang}']",
                            message=f"Duplicate title for locale '{lang}'.",
                            line=t.sourceline,
                        )
                    )
                else:
                    seen_locales.add(lang)
                if not (t.text or "").strip():
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            field=f"{locator}/media:title",
                            message="<media:title> element is empty.",
                            line=t.sourceline,
                        )
                    )
            if len(seen_locales) < 2:
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        field=f"{locator}/media:title",
                        message="Only one localized title provided; most territories require 2+ locales.",
                        line=item.sourceline,
                    )
                )

        thumb = item.find("media:thumbnail", namespaces=ns)
        if thumb is None or not thumb.get("url"):
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"{locator}/media:thumbnail",
                    message="Missing <media:thumbnail url=\"...\"/>.",
                    line=item.sourceline,
                )
            )
        else:
            url = thumb.get("url")
            if not url.startswith(("http://", "https://")):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        field=f"{locator}/media:thumbnail",
                        message=f"Thumbnail URL is not absolute http(s): '{url}'.",
                        line=thumb.sourceline,
                    )
                )

        schedule = item.find("epg:schedule", namespaces=ns)
        if schedule is None:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"{locator}/epg:schedule",
                    message="Missing <epg:schedule> — no EPG airing information for this asset.",
                    line=item.sourceline,
                )
            )
        else:
            airings = schedule.findall("epg:airing", namespaces=ns)
            if not airings:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        field=f"{locator}/epg:schedule",
                        message="<epg:schedule> has no <epg:airing> entries.",
                        line=schedule.sourceline,
                    )
                )
            for a_idx, airing in enumerate(airings):
                start = _parse_iso8601(airing.get("start"))
                end = _parse_iso8601(airing.get("end"))
                a_locator = f"{locator}/epg:schedule/epg:airing[{a_idx}]"
                if start is None:
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            field=a_locator,
                            message=f"Invalid or missing start time: '{airing.get('start')}' (expected ISO 8601).",
                            line=airing.sourceline,
                        )
                    )
                if end is None:
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            field=a_locator,
                            message=f"Invalid or missing end time: '{airing.get('end')}' (expected ISO 8601).",
                            line=airing.sourceline,
                        )
                    )
                if start and end and start >= end:
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            field=a_locator,
                            message="EPG airing start time is not before end time.",
                            line=airing.sourceline,
                        )
                    )

        window = item.find("licensing:window", namespaces=ns)
        if window is None:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"{locator}/licensing:window",
                    message="Missing <licensing:window> — rights/availability dates are required before go-live.",
                    line=item.sourceline,
                )
            )
        else:
            start = _parse_iso8601(window.get("start"))
            end = _parse_iso8601(window.get("end"))
            w_locator = f"{locator}/licensing:window"
            if start is None:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        field=w_locator,
                        message=f"Invalid or missing licensing start date: '{window.get('start')}'.",
                        line=window.sourceline,
                    )
                )
            if end is None:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        field=w_locator,
                        message=f"Invalid or missing licensing end date: '{window.get('end')}'.",
                        line=window.sourceline,
                    )
                )
            if start and end:
                if start >= end:
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            field=w_locator,
                            message="Licensing window start date is not before end date.",
                            line=window.sourceline,
                        )
                    )
                elif end < datetime.now(timezone.utc):
                    issues.append(
                        Issue(
                            severity=Severity.WARNING,
                            field=w_locator,
                            message="Licensing window has already expired.",
                            line=window.sourceline,
                        )
                    )
            if not window.get("territories"):
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        field=w_locator,
                        message="No territories declared; asset will be treated as globally licensed.",
                        line=window.sourceline,
                    )
                )

    passed = not any(i.severity == Severity.ERROR for i in issues)
    return MetadataReport(
        passed=passed,
        feed_format=FeedFormat.MRSS,
        items_checked=len(items),
        issues=issues,
    )


def validate_json_feed(raw: bytes) -> MetadataReport:
    issues: list[Issue] = []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return MetadataReport(
            passed=False,
            feed_format=FeedFormat.JSON,
            items_checked=0,
            issues=[
                Issue(
                    severity=Severity.ERROR,
                    field="document",
                    message=f"Invalid JSON: {exc.msg}",
                    line=exc.lineno,
                )
            ],
        )

    items = data.get("items") if isinstance(data, dict) else None
    if items is None:
        return MetadataReport(
            passed=False,
            feed_format=FeedFormat.JSON,
            items_checked=0,
            issues=[
                Issue(
                    severity=Severity.ERROR,
                    field="$.items",
                    message="Top-level JSON object must contain an 'items' array.",
                )
            ],
        )

    for idx, item in enumerate(items):
        locator = f"$.items[{idx}]"
        if not item.get("content_id"):
            issues.append(
                Issue(severity=Severity.ERROR, field=f"{locator}.content_id", message="Missing content_id.")
            )

        titles = item.get("titles") or {}
        if not titles:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"{locator}.titles",
                    message="No localized titles found ('titles' must be a non-empty locale -> title map).",
                )
            )
        else:
            for locale, title in titles.items():
                if not str(title or "").strip():
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            field=f"{locator}.titles.{locale}",
                            message="Localized title is empty.",
                        )
                    )
            if len(titles) < 2:
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        field=f"{locator}.titles",
                        message="Only one localized title provided; most territories require 2+ locales.",
                    )
                )

        thumb = item.get("thumbnail_url")
        if not thumb:
            issues.append(
                Issue(severity=Severity.ERROR, field=f"{locator}.thumbnail_url", message="Missing thumbnail_url.")
            )
        elif not str(thumb).startswith(("http://", "https://")):
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    field=f"{locator}.thumbnail_url",
                    message=f"thumbnail_url is not absolute http(s): '{thumb}'.",
                )
            )

        epg = item.get("epg") or []
        if not epg:
            issues.append(
                Issue(severity=Severity.ERROR, field=f"{locator}.epg", message="No EPG airings provided.")
            )
        for a_idx, airing in enumerate(epg):
            start = _parse_iso8601(airing.get("start"))
            end = _parse_iso8601(airing.get("end"))
            a_locator = f"{locator}.epg[{a_idx}]"
            if start is None:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        field=a_locator,
                        message=f"Invalid or missing start time: '{airing.get('start')}'.",
                    )
                )
            if end is None:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        field=a_locator,
                        message=f"Invalid or missing end time: '{airing.get('end')}'.",
                    )
                )
            if start and end and start >= end:
                issues.append(
                    Issue(severity=Severity.ERROR, field=a_locator, message="EPG start time is not before end time.")
                )

        window = item.get("licensing_window")
        w_locator = f"{locator}.licensing_window"
        if not window:
            issues.append(
                Issue(severity=Severity.ERROR, field=w_locator, message="Missing licensing_window.")
            )
        else:
            start = _parse_iso8601(window.get("start"))
            end = _parse_iso8601(window.get("end"))
            if start is None:
                issues.append(
                    Issue(severity=Severity.ERROR, field=w_locator, message=f"Invalid start date: '{window.get('start')}'.")
                )
            if end is None:
                issues.append(
                    Issue(severity=Severity.ERROR, field=w_locator, message=f"Invalid end date: '{window.get('end')}'.")
                )
            if start and end:
                if start >= end:
                    issues.append(
                        Issue(severity=Severity.ERROR, field=w_locator, message="Licensing start date is not before end date.")
                    )
                elif end < datetime.now(timezone.utc):
                    issues.append(
                        Issue(severity=Severity.WARNING, field=w_locator, message="Licensing window has already expired.")
                    )
            if not window.get("territories"):
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        field=w_locator,
                        message="No territories declared; asset will be treated as globally licensed.",
                    )
                )

    passed = not any(i.severity == Severity.ERROR for i in issues)
    return MetadataReport(passed=passed, feed_format=FeedFormat.JSON, items_checked=len(items), issues=issues)
