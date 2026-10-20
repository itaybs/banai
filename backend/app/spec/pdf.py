"""Renders a SpecContent to PDF bytes with fpdf2 (HarfBuzz shaping, right-to-left for Hebrew) and the
embedded BanaiSans font (Noto Sans + Noto Sans Hebrew, see scripts/build_spec_font.py). Every page
carries the "visual design draft, verify on site" disclaimer in its footer."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from PIL import Image

from app.spec.content import SpecContent

FONTS = Path(__file__).parent / "fonts"
FONT = "banai"
INDENT_MM = 6
LINE_MM = 5.6
IMAGE_MAX_W_MM = 95
IMAGE_MAX_H_MM = 95

INK = (33, 33, 33)
MUTED = (110, 110, 110)
ACCENT = (161, 79, 36)
WARNING = (150, 60, 0)
BOX_FILL = (253, 240, 210)
BOX_BORDER = (190, 140, 40)


class _SpecPDF(FPDF):
    def __init__(self, content: SpecContent, total_pages: int | None):
        super().__init__(format="A4")
        self.content = content
        self.total_pages = total_pages
        self.rtl = content.language == "he"
        self.align = "R" if self.rtl else "L"
        self.add_font(FONT, "", FONTS / "BanaiSans-Regular.ttf")
        self.add_font(FONT, "B", FONTS / "BanaiSans-Bold.ttf")
        if self.rtl:
            self.set_text_shaping(use_shaping_engine=True, direction="rtl", script="hebr", language="heb")
        else:
            self.set_text_shaping(use_shaping_engine=True, direction="ltr", script="latn", language="eng")
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(auto=True, margin=22)
        self.set_title(content.title)
        self.set_author("BanAI")
        self.set_creator("BanAI design summary")
        self.set_lang(content.language)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font(FONT, "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 4, self.content.disclaimer_short, align="C", new_x="LMARGIN", new_y="NEXT")
        # The total is known from a first pass: fpdf2's "{nb}" alias is replaced after shaping and
        # left a wide gap in right-to-left text.
        if self.total_pages:
            self.cell(0, 4, self.content.footer_page.format(page=self.page_no(), pages=self.total_pages), align="C")

    # ---- building blocks ----
    def text_line(self, text: str, *, size: float = 10.5, bold: bool = False, color=INK, indent: int = 0, height: float = LINE_MM) -> None:
        self.set_font(FONT, "B" if bold else "", size)
        self.set_text_color(*color)
        shift = indent * INDENT_MM
        self.set_x(self.l_margin + (0 if self.rtl else shift))
        self.multi_cell(self.epw - shift, height, text, align=self.align, new_x="LMARGIN", new_y="NEXT")

    def heading(self, text: str) -> None:
        if self.get_y() > self.h - 50:  # keep a heading with at least a few of its lines
            self.add_page()
        self.ln(3)
        self.text_line(text, size=13, bold=True, color=ACCENT, height=7)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)

    def disclaimer_box(self, text: str) -> None:
        self.set_font(FONT, "B", 10.5)
        self.set_text_color(*INK)
        self.set_fill_color(*BOX_FILL)
        self.set_draw_color(*BOX_BORDER)
        self.set_line_width(0.4)
        self.multi_cell(0, 6, text, border=1, fill=True, align=self.align, padding=3, new_x="LMARGIN", new_y="NEXT")

    def front_image(self, png: bytes, caption: str) -> None:
        with Image.open(BytesIO(png)) as image:
            width_px, height_px = image.size
        width = min(IMAGE_MAX_W_MM, IMAGE_MAX_H_MM * width_px / height_px)
        height = width * height_px / width_px
        if self.get_y() + height + 10 > self.h - self.b_margin:
            self.add_page()
        self.image(BytesIO(png), x=(self.w - width) / 2, y=self.get_y(), w=width, h=height)
        self.set_y(self.get_y() + height + 1.5)
        self.set_font(FONT, "", 8.5)
        self.set_text_color(*MUTED)
        self.cell(0, 4.5, caption, align="C", new_x="LMARGIN", new_y="NEXT")


def render_pdf(content: SpecContent, front_png: bytes | None = None) -> bytes:
    first = _build(content, front_png, total_pages=None)  # counts the pages
    pages = first.pages_count
    _close_fonts(first)
    final = _build(content, front_png, total_pages=pages)
    try:
        return bytes(final.output())
    finally:
        _close_fonts(final)


def _close_fonts(pdf: _SpecPDF) -> None:
    """fpdf2 keeps each font file open through fontTools; close them once the PDF is built."""
    for font in pdf.fonts.values():
        if getattr(font, "ttfont", None) is not None:
            font.ttfont.close()


def _build(content: SpecContent, front_png: bytes | None, total_pages: int | None) -> _SpecPDF:
    pdf = _SpecPDF(content, total_pages)
    pdf.add_page()
    pdf.text_line(content.title, size=20, bold=True, height=10)
    pdf.text_line(content.meta, size=10, color=MUTED)
    if content.prepared_for:
        pdf.text_line(content.prepared_for, size=10, color=MUTED)
    pdf.ln(3)
    pdf.disclaimer_box(content.disclaimer)
    if front_png:
        pdf.ln(4)
        pdf.front_image(front_png, content.image_caption)
    for section in content.sections:
        pdf.heading(section.title)
        for index, line in enumerate(section.lines):
            if line.bold and line.indent == 0:  # a block heading (e.g. a compartment): keep it with its items
                items = 0
                for following in section.lines[index + 1:]:
                    if following.indent == 0:
                        break
                    items += 1
                if pdf.get_y() + (items + 1) * LINE_MM > pdf.page_break_trigger:
                    pdf.add_page()
            pdf.text_line(line.text, bold=line.bold, indent=line.indent, color=WARNING if line.warning else INK)
    return pdf
