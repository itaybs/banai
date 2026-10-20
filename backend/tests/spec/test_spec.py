"""Design summary PDF for the carpenter: content, rendering and the /api/spec/pdf endpoint."""

from __future__ import annotations

import base64
import json
import logging
from datetime import date
from io import BytesIO

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.agent.tools import PRODUCTION_CLAIM
from app.api.agent import get_llm_client
from app.config import get_settings, get_signing_key
from app.domain.apply import apply_ops
from app.domain.catalog import load_catalog
from app.domain.defaults import basic_wardrobe
from app.main import create_app
from app.spec.content import Preferences, build_content
from app.spec.pdf import render_pdf
from app.spec.summary import TOOL
from tests.agent.fakes import FakeClient, completion, tool_call

CATALOG = load_catalog()
RAIL_180_LEFT = {"op": "add_rail", "compartmentId": "cmp_left", "y": 1800, "id": "rail_l1"}  # 18.2 cm free


def design(*ops):
    return apply_ops(basic_wardrobe(), list(ops), CATALOG)


def content(language="he", ops=(), preferences=Preferences(), summary=None, d=None):
    return build_content(d or design(*ops), CATALOG, revision=3, language=language, preferences=preferences,
                         summary=summary, today=date(2026, 10, 20))


def lines(spec, title):
    return [line.text for section in spec.sections if section.title == title for line in section.lines]


def pdf_text(pdf: bytes) -> list[str]:
    document = pdfium.PdfDocument(pdf)
    return [document[i].get_textpage().get_text_range() for i in range(len(document))]


def plain(text: str) -> str:
    """pypdfium2 returns Hebrew in reading order but leaves neutral marks in visual positions
    (")…(", "תא :1"), so Hebrew text is compared without parentheses and colons."""
    return text.replace("(", "").replace(")", "").replace(":", "")


def png(width=60, height=80) -> bytes:
    out = BytesIO()
    Image.new("RGB", (width, height), (120, 85, 60)).save(out, format="PNG")
    return out.getvalue()


# ---- content: every number from the design ----

def test_hebrew_content_from_the_design():
    spec = content("he", [RAIL_180_LEFT])
    assert lines(spec, "מידות כלליות")[0] == 'רוחב 200 ס"מ · גובה 240 ס"מ · עומק 60 ס"מ'
    compartments = lines(spec, "תאים (משמאל לימין)")
    left = compartments[compartments.index('תא 1 · רוחב 64.3 ס"מ') + 1:compartments.index('תא 2 · רוחב 64.3 ס"מ')]
    assert left == ['מדף בגובה 40 ס"מ', 'מדף בגובה 80 ס"מ', 'מדף בגובה 120 ס"מ', 'מדף בגובה 160 ס"מ',
                    'מוט תלייה בגובה 180 ס"מ (מתחתיו 18.2 ס"מ פנויים)']  # bottom to top
    assert 'מגירה: 0–20 ס"מ' in compartments and 'מגירה: 20–40 ס"מ' in compartments
    assert lines(spec, "הערות מרווח") == ['תא 1: מתחת למוט בגובה 180 ס"מ נשארים רק 18.2 ס"מ פנויים לתלייה.']
    assert lines(spec, "דלתות")[:2] == ["דלתות ציר · 3 דלתות", "דלת 1: תא 1 · ציר בצד שמאל"]
    assert lines(spec, "חומרים, צבעים וגימורים")[0] == "גוף, מדפים ומגירות: מלמין, לבן, גימור מט"
    assert spec.meta == "תאריך: 20.10.2026 · גרסת עיצוב: 3"


def test_english_content_and_door_variants():
    spec = content("en", [{"op": "configure_doors", "type": "sliding", "count": 3},
                          {"op": "set_material", "target": "doors", "color": {"catalogId": "walnut"}}])
    assert lines(spec, "Doors") == ["Sliding doors · 3 panels"]
    assert lines(spec, "Materials, colours and finishes")[1] == "Doors: Melamine board, Walnut, Matte finish"
    assert lines(spec, "Clearance notes") == ["None."]
    no_doors = content("en", [{"op": "configure_doors", "type": "none"}])
    assert lines(no_doors, "Doors") == ["No doors"]
    assert not any(text.startswith("Doors:") for text in lines(no_doors, "Materials, colours and finishes"))


def test_custom_colour_and_shelves_too_close():
    spec = content("en", [{"op": "set_material", "target": "carcass", "color": {"custom": True, "name": "Sage", "hex": "#9caf88"}},
                          {"op": "add_shelf", "compartmentId": "cmp_left", "y": 1000, "id": "shf_new"}])
    assert lines(spec, "Materials, colours and finishes")[0] == "Carcass, shelves and drawers: Melamine board, Sage (#9caf88), Matte finish"
    assert "Compartment 1: only 18.2 cm between the shelves at 80 and 100 cm." in lines(spec, "Clearance notes")


def test_preferences_name_and_summary_only_when_given():
    plain = content("he")
    assert plain.prepared_for is None
    assert "העדפות והערות הלקוח" not in [s.title for s in plain.sections]
    assert "סיכום (נכתב על ידי AI)" not in [s.title for s in plain.sections]
    full = content("he", preferences=Preferences(intended_use="kids", location="חדר ילדים", name="דנה"), summary="ארון לבן.")
    assert full.prepared_for == "הוכן עבור: דנה"
    assert lines(full, "העדפות והערות הלקוח") == ["שימוש מתוכנן: חדר ילדים", "מיקום ההתקנה: חדר ילדים"]
    assert lines(full, "סיכום (נכתב על ידי AI)") == ["ארון לבן."]


@pytest.mark.parametrize("language", ["he", "en"])
def test_the_disclaimer_is_there_and_no_text_claims_production_readiness(language):
    spec = content(language, [RAIL_180_LEFT])
    assert ("לא שרטוט ייצור" if language == "he" else "not a manufacturing drawing") in spec.disclaimer
    assert ("לאמת את כל המידות במקום" if language == "he" else "verify every measurement on site") in spec.disclaimer
    assert not [text for text in spec.texts() if PRODUCTION_CLAIM.search(text)]


# ---- the PDF itself ----

@pytest.mark.parametrize(("language", "footer", "page"), [
    ("he", "טיוטת עיצוב חזותית, לא שרטוט ייצור. יש לאמת את כל המידות במקום.", "עמוד {} מתוך {}"),
    ("en", "Visual design draft, not a manufacturing drawing. Verify all measurements on site.", "Page {} of {}"),
])
def test_every_page_has_the_disclaimer_and_a_page_number(language, footer, page):
    pdf = render_pdf(content(language, [RAIL_180_LEFT], Preferences(requests="x" * 400)), png())
    assert pdf.startswith(b"%PDF")
    pages = pdf_text(pdf)
    assert len(pages) >= 2
    for number, text in enumerate(pages, start=1):
        assert footer in text and page.format(number, len(pages)) in text
    assert "{nb}" not in "".join(pages)


def test_the_font_and_the_image_are_embedded():
    with_image, without = render_pdf(content("he"), png()), render_pdf(content("he"))
    assert b"FontFile2" in with_image and b"NotoSans" in with_image  # BanaiSans (Noto Sans + Noto Sans Hebrew)
    assert b"/Subtype /Image" in with_image and b"/Subtype /Image" not in without


def test_hebrew_text_comes_out_in_reading_order():
    text = plain(pdf_text(render_pdf(content("he", [RAIL_180_LEFT])))[0])
    assert 'רוחב 200 ס"מ · גובה 240 ס"מ · עומק 60 ס"מ' in text
    assert plain('מוט תלייה בגובה 180 ס"מ (מתחתיו 18.2 ס"מ פנויים)') in text
    assert plain('תא 1: מתחת למוט בגובה 180 ס"מ נשארים רק 18.2 ס"מ פנויים לתלייה.') in text


# ---- the endpoint ----

@pytest.fixture
def client_for(monkeypatch):
    def build(fake):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("PROPOSAL_SIGNING_KEY", "test-signing-key")
        get_settings.cache_clear()
        get_signing_key.cache_clear()
        app = create_app()
        app.dependency_overrides[get_llm_client] = lambda: fake
        return TestClient(app)

    yield build
    get_settings.cache_clear()
    get_signing_key.cache_clear()


def body(language="he", **extra):
    return {"design": design(RAIL_180_LEFT), "revision": 4, "language": language, **extra}


def summary_reply(text):
    return completion(calls=[tool_call(TOOL, {"summary": text})])


def test_returns_a_pdf_download_with_the_model_summary(client_for):
    fake = FakeClient(summary_reply("ארון לבן ברוחב 200 ס\"מ עם מדפים משמאל."))
    response = client_for(fake).post("/api/spec/pdf", json=body(frontImage="data:image/png;base64," + base64.b64encode(png()).decode()))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="banai-design-r4.pdf"'
    assert response.headers["cache-control"] == "no-store"
    text = plain("".join(pdf_text(response.content)))
    assert 'ארון לבן ברוחב 200 ס"מ עם מדפים משמאל.' in text and plain("סיכום (נכתב על ידי AI)") in text
    facts = json.loads(fake.requests[0]["messages"][1]["content"])  # the model gets the exact lines as data
    assert any('מוט תלייה בגובה 180 ס"מ (מתחתיו 18.2 ס"מ פנויים)' in section["lines"] for section in facts)


def test_a_summary_with_a_production_claim_is_left_out(client_for):
    fake = FakeClient(summary_reply("העיצוב מוכן לייצור."))
    response = client_for(fake).post("/api/spec/pdf", json=body())
    assert response.status_code == 200
    text = plain("".join(pdf_text(response.content)))
    assert "מוכן לייצור" not in text and plain("סיכום (נכתב על ידי AI)") not in text


def test_no_model_call_when_the_summary_is_off_or_the_agent_is_down(client_for, caplog):
    fake = FakeClient()
    assert client_for(fake).post("/api/spec/pdf", json=body(includeSummary=False)).status_code == 200
    assert fake.requests == []
    failing = FakeClient(error=RuntimeError("provider said sk-abc123"))
    with caplog.at_level(logging.WARNING, logger="app.spec.summary"):
        response = client_for(failing).post("/api/spec/pdf", json=body())
    assert response.status_code == 200  # the PDF never depends on the summary
    assert "sk-abc123" not in caplog.text and "spec summary failed: RuntimeError" in caplog.text
    assert client_for(None).post("/api/spec/pdf", json=body()).status_code == 200  # no OpenAI key at all


def test_personal_details_only_when_typed(client_for):
    plain = "".join(pdf_text(client_for(None).post("/api/spec/pdf", json=body("en")).content))
    assert "Prepared for" not in plain
    named = client_for(None).post("/api/spec/pdf", json=body("en", preferences={"name": "Dana Cohen", "intendedUse": "clothes"}))
    text = "".join(pdf_text(named.content))
    assert "Prepared for: Dana Cohen" in text and "Intended use: Clothes" in text


@pytest.mark.parametrize("image", [
    "not a data url",
    "data:image/png;base64,!!!not-base64!!!",
    "data:image/png;base64," + base64.b64encode(b"GIF89a fake").decode(),
    "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"broken").decode(),
    "data:image/png;base64," + base64.b64encode(png(5000, 10)).decode(),  # too wide
])
def test_bad_images_are_rejected(client_for, image):
    response = client_for(None).post("/api/spec/pdf", json=body(frontImage=image))
    assert response.status_code == 422 and response.json()["error"]["code"] == "IMAGE_INVALID"


def test_requests_are_validated(client_for):
    client = client_for(None)
    no_language = body()
    del no_language["language"]
    assert client.post("/api/spec/pdf", json=no_language).status_code == 422
    assert client.post("/api/spec/pdf", json=body("fr")).status_code == 422
    broken = body()
    broken["design"]["dimensions"]["width"] = 10
    assert client.post("/api/spec/pdf", json=broken).status_code == 422
    assert client.post("/api/spec/pdf", json=body(preferences={"requests": "x" * 501})).status_code == 422
    assert client.post("/api/spec/pdf", json=body(preferences={"budget": "5000"})).status_code == 422  # no pricing fields


def test_customer_text_cannot_claim_production_readiness(client_for):
    response = client_for(None).post("/api/spec/pdf", json=body(preferences={"requests": "העיצוב מוכן לייצור"}))
    assert response.status_code == 422 and response.json()["error"]["code"] == "TEXT_CLAIM"
    ok = client_for(None).post("/api/spec/pdf", json=body(preferences={"requests": "ההצעה מוכנה לאישור"}))
    assert ok.status_code == 200
