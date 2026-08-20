from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class FeedFormat(str, Enum):
    MRSS = "mrss"
    JSON = "json"


class Issue(BaseModel):
    """A single validation finding, shaped for self-service troubleshooting."""

    severity: Severity
    field: str = Field(..., description="Dot-path or XPath-like locator, e.g. item[2]/media:thumbnail")
    message: str
    line: Optional[int] = Field(None, description="Source line number, when the parser can determine one")


class MetadataReport(BaseModel):
    passed: bool
    feed_format: FeedFormat
    items_checked: int
    issues: list[Issue]


class RenditionInfo(BaseModel):
    resolution_label: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    bandwidth: Optional[int] = None
    codecs: Optional[str] = None
    uri: str


class AudioTrackInfo(BaseModel):
    group_id: str
    name: str
    language: Optional[str] = None
    uri: Optional[str] = None


class SegmentCheck(BaseModel):
    uri: str
    ok: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


class ManifestReport(BaseModel):
    passed: bool
    manifest_type: str  # "hls" | "dash"
    manifest_url: str
    renditions: list[RenditionInfo]
    audio_tracks: list[AudioTrackInfo]
    missing_required_renditions: list[str]
    segments_checked: int
    broken_segments: list[SegmentCheck]
    issues: list[Issue]


class CombinedReport(BaseModel):
    partner_name: str
    content_title: Optional[str] = None
    passed: bool
    metadata_report: Optional[MetadataReport] = None
    manifest_report: Optional[ManifestReport] = None
