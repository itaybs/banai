"""Builds the PDF font (BanaiSans) by merging Noto Sans (Latin, digits) with Noto Sans Hebrew.

One merged font, not a fallback pair: fpdf2 split Hebrew words where it switched fonts mid-cell
(e.g. "מדפי ם:"). Both fonts are SIL OFL 1.1 (app/spec/fonts/OFL.txt) and have no reserved name.

Sources (static, hinted TTF), from https://github.com/notofonts/notofonts.github.io/tree/main/fonts:
  NotoSans/hinted/ttf/NotoSans-{Regular,Bold}.ttf
  NotoSansHebrew/hinted/ttf/NotoSansHebrew-{Regular,Bold}.ttf

Usage (from backend/): uv run python scripts/build_spec_font.py <folder with the four source fonts>
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.merge import Merger

OUT = Path(__file__).resolve().parent.parent / "app" / "spec" / "fonts"


def main(source: Path) -> None:
    for style in ("Regular", "Bold"):
        merged = Merger().merge([str(source / f"NotoSans-{style}.ttf"), str(source / f"NotoSansHebrew-{style}.ttf")])
        merged.save(OUT / f"BanaiSans-{style}.ttf")
        print("wrote", OUT / f"BanaiSans-{style}.ttf")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
