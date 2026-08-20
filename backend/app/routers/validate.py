from __future__ import annotations

import httpx
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from app.models import CombinedReport, FeedFormat
from app.validators.manifest import validate_manifest
from app.validators.metadata import validate_json_feed, validate_mrss

router = APIRouter(prefix="/api/validate", tags=["validate"])


def _get_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@router.post("/metadata")
async def validate_metadata(
    feed_format: FeedFormat = Form(...),
    content: str | None = Form(None),
    file: UploadFile | None = None,
):
    if file is not None:
        raw = await file.read()
    elif content is not None:
        raw = content.encode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="Provide either 'content' or a 'file' upload.")

    if feed_format == FeedFormat.MRSS:
        return validate_mrss(raw)
    return validate_json_feed(raw)


@router.post("/manifest")
async def validate_manifest_endpoint(request: Request, manifest_url: str = Form(...)):
    client = _get_client(request)
    return await validate_manifest(manifest_url, client)


@router.post("/submission", response_model=CombinedReport)
async def validate_submission(
    request: Request,
    partner_name: str = Form(...),
    content_title: str | None = Form(None),
    feed_format: FeedFormat | None = Form(None),
    metadata_content: str | None = Form(None),
    manifest_url: str | None = Form(None),
):
    if not metadata_content and not manifest_url:
        raise HTTPException(status_code=400, detail="Provide at least one of metadata_content or manifest_url.")

    metadata_report = None
    if metadata_content and feed_format:
        raw = metadata_content.encode("utf-8")
        metadata_report = validate_mrss(raw) if feed_format == FeedFormat.MRSS else validate_json_feed(raw)

    manifest_report = None
    if manifest_url:
        client = _get_client(request)
        manifest_report = await validate_manifest(manifest_url, client)

    passed = all(
        r is None or r.passed for r in (metadata_report, manifest_report)
    ) and (metadata_report is not None or manifest_report is not None)

    return CombinedReport(
        partner_name=partner_name,
        content_title=content_title,
        passed=passed,
        metadata_report=metadata_report,
        manifest_report=manifest_report,
    )
