"""Design summary PDF for the carpenter. A visual design draft, never a manufacturing file: every number
comes from the validated design, the model may add one short checked paragraph, and every page says to
verify all measurements on site. Nothing is stored; no personal data except an optional typed name."""

from __future__ import annotations

import base64
import binascii
import logging
from datetime import date
from io import BytesIO
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app.agent.language import Language
from app.agent.tools import PRODUCTION_CLAIM, Text
from app.api.agent import _canonical, error, get_llm_client, localized
from app.config import Settings, get_settings
from app.domain.catalog import load_catalog
from app.domain.errors import DomainError
from app.spec.content import Preferences, build_content
from app.spec.pdf import render_pdf
from app.spec.summary import write_summary

router = APIRouter(prefix="/api/spec")
log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 1_500_000
MAX_IMAGE_SIDE = 4096
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
DATA_URL_PREFIX = "data:image/png;base64,"


class SpecPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intendedUse: Literal["clothes", "kids", "linen", "mixed"] | None = None
    location: Text(200) | None = None
    timeline: Text(100) | None = None
    requests: Text(500) | None = None
    name: Text(80) | None = None


class SpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design: dict
    revision: Annotated[int, Field(ge=1)]
    language: Language
    preferences: SpecPreferences = SpecPreferences()
    # The front view captured from the 3D viewer, as a PNG data URL (labelled illustrative in the PDF).
    frontImage: Annotated[str, Field(max_length=len(DATA_URL_PREFIX) + MAX_IMAGE_BYTES * 4 // 3 + 4)] | None = None
    includeSummary: bool = True


def _decode_png(data_url: str) -> bytes | None:
    """The PNG bytes, or None when it is not a small, valid PNG."""
    if not data_url.startswith(DATA_URL_PREFIX):
        return None
    try:
        png = base64.b64decode(data_url[len(DATA_URL_PREFIX):], validate=True)
    except (binascii.Error, ValueError):
        return None
    if not png.startswith(PNG_MAGIC) or len(png) > MAX_IMAGE_BYTES:
        return None
    try:
        with Image.open(BytesIO(png)) as image:
            image.verify()
            width, height = image.size
    except Exception:
        return None
    return png if 0 < width <= MAX_IMAGE_SIDE and 0 < height <= MAX_IMAGE_SIDE else None


@router.post("/pdf")
def spec_pdf(
    request: SpecRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[Any, Depends(get_llm_client)],
):
    catalog = load_catalog()
    try:
        design = _canonical(request.design, catalog)
    except DomainError as exc:
        return error(422, exc.code, exc.message, exc.path)
    png = None
    if request.frontImage is not None:
        png = _decode_png(request.frontImage)
        if png is None:
            return localized(422, "IMAGE_INVALID", request.language)
    prefs = request.preferences
    customer_texts = [prefs.location, prefs.timeline, prefs.requests, prefs.name]
    if any(text and PRODUCTION_CLAIM.search(text) for text in customer_texts):
        return localized(422, "TEXT_CLAIM", request.language)

    preferences = Preferences(intended_use=prefs.intendedUse, location=prefs.location, timeline=prefs.timeline,
                              requests=prefs.requests, name=prefs.name)
    content = build_content(design, catalog, revision=request.revision, language=request.language,
                            preferences=preferences, summary=None, today=date.today())
    summary = write_summary(client, settings.chat_model, content) if request.includeSummary and client else None
    if summary:
        content = build_content(design, catalog, revision=request.revision, language=request.language,
                                preferences=preferences, summary=summary, today=date.today())
    # Defence in depth: nothing in the document may claim production readiness or approval.
    if any(PRODUCTION_CLAIM.search(text) for text in content.texts()):
        log.warning("spec pdf blocked: production claim in content")
        return localized(422, "TEXT_CLAIM", request.language)

    pdf = render_pdf(content, png)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="banai-design-r{request.revision}.pdf"',
            "Cache-Control": "no-store",
        },
    )
