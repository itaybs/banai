"""Development preview of the design summary PDF: builds a Hebrew and an English sample and renders
every page to PNG, so the layout (RTL order, numbers and units, font, disclaimer) can be checked by eye.

Usage (from backend/): uv run python scripts/render_spec_preview.py <output folder> [front.png]
Needs the dev dependency pypdfium2. Not used by the app."""

from __future__ import annotations

import sys
from datetime import date
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.apply import apply_ops  # noqa: E402
from app.domain.catalog import load_catalog  # noqa: E402
from app.domain.defaults import basic_wardrobe  # noqa: E402
from app.spec.content import Preferences, build_content  # noqa: E402
from app.spec.pdf import render_pdf  # noqa: E402

SAMPLE_OPS = [
    {"op": "add_rail", "compartmentId": "cmp_left", "y": 1800, "id": "rail_l1"},  # 18.2 cm free: a clearance note
    {"op": "set_material", "target": "doors", "color": {"catalogId": "walnut"}},
]
PREFERENCES = {
    "he": Preferences(intended_use="mixed", location="חדר שינה, נישה בין שני קירות, פאנל של 10 ס\"מ בתחתית",
                      timeline="עד סוף דצמבר", requests="ידיות שקועות, תאורה בתא האמצעי", name="דנה כהן"),
    "en": Preferences(intended_use="clothes", location="Bedroom niche, 10 cm skirting board", timeline="By end of December",
                      requests="Recessed handles", name="Dana Cohen"),
}
SUMMARY = {
    "he": "ארון לבן ברוחב 200 ס\"מ עם דלתות ציר בגוון אגוז: מדפים משמאל, תלייה באמצע ומגירות מימין.",
    "en": "A 200 cm white wardrobe with walnut hinged doors: shelves on the left, hanging in the middle and drawers on the right.",
}


def placeholder_front() -> bytes:
    """A stand-in for the 3D capture (the app sends the real one)."""
    image = Image.new("RGB", (900, 1000), (236, 233, 228))
    draw = ImageDraw.Draw(image)
    draw.rectangle((150, 80, 750, 960), fill=(120, 85, 60), outline=(60, 40, 30), width=6)
    for x in (350, 550):
        draw.line((x, 80, x, 960), fill=(60, 40, 30), width=6)
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def main(out_dir: Path, front: Path | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    design = apply_ops(basic_wardrobe(), SAMPLE_OPS, catalog)
    png = front.read_bytes() if front else placeholder_front()
    for language in ("he", "en"):
        content = build_content(design, catalog, revision=5, language=language, preferences=PREFERENCES[language],
                                summary=SUMMARY[language], today=date(2026, 10, 20))
        pdf_bytes = render_pdf(content, png)
        pdf_path = out_dir / f"spec-{language}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        document = pdfium.PdfDocument(pdf_bytes)
        for index in range(len(document)):
            document[index].render(scale=1.5).to_pil().save(out_dir / f"spec-{language}-{index + 1}.png")
        print(pdf_path, f"{len(pdf_bytes) // 1024} KB, {len(document)} pages")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
