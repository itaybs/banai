---
project: BanAI
type: technical
tags: [banai, fork, spec-pdf, rtl, hebrew]
---

# Hebrew RTL and Font

Back to [[00 - Fork Additions]].

## The setup
- **fpdf2** (2.8.9) with **HarfBuzz** text shaping (`uharfbuzz`) and right-to-left direction for Hebrew. Chosen for low memory: no headless browser, no GTK/Pango.
- One embedded font, **BanaiSans** (Regular and Bold), in `backend/app/spec/fonts/`, with its licence `OFL.txt`.
- BanaiSans is **Noto Sans** (Latin and digits) merged with **Noto Sans Hebrew**. Both are SIL Open Font License 1.1 with no reserved font name.

## How to rebuild the font
1. Download the four static, hinted TTF files from https://github.com/notofonts/notofonts.github.io/tree/main/fonts:
   - `NotoSans/hinted/ttf/NotoSans-Regular.ttf` and `NotoSans-Bold.ttf`
   - `NotoSansHebrew/hinted/ttf/NotoSansHebrew-Regular.ttf` and `NotoSansHebrew-Bold.ttf`
2. From `backend/`: `uv run python scripts/build_spec_font.py <folder with the four files>`
3. It writes `app/spec/fonts/BanaiSans-Regular.ttf` and `BanaiSans-Bold.ttf`. The source files do not go in the repo.

## Problems it solved
- **Split Hebrew words**: Noto Sans Hebrew has no digits or Latin letters. With a Latin fallback font, fpdf2 split words where it switched fonts mid-line (for example "מדפי ם:"). One merged font removed the switching.
- **Page numbers in RTL**: fpdf2's `{nb}` placeholder left a wide gap in Hebrew. The PDF is now rendered twice: the first pass counts the pages, the second writes "עמוד 1 מתוך 2".
- **Open font files**: fpdf2 kept the font files open through fontTools. They are now closed after each render.
- **Orphan headings**: a compartment heading could sit alone at the bottom of a page. A heading now moves to the next page together with its items.

## Checking it by eye
- From `backend/`: `uv run python scripts/render_spec_preview.py <output folder>` writes a Hebrew and an English sample PDF, and a PNG of every page.
- Check the RTL order, numbers with units ("120 ס\"מ"), the font, the disclaimer box and every page footer.
- Note for tests: pypdfium2 returns Hebrew in reading order but leaves neutral marks in visual positions (")…(", "תא :1"). The tests compare Hebrew text without parentheses and colons.
