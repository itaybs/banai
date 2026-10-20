"""Design summary for the carpenter: the validated design -> titled sections of text lines, in the
chat's language. Every number comes from the design (and the clearance code), never from model text.
No PDF code here (see pdf.py); this is what the tests check.

This is a visual design draft, not a manufacturing file: no cut lists, board sizes, hardware or prices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.agent.clearances import cm, design_issues, free_below
from app.agent.language import Language
from app.domain.geometry import interior_height, interior_width

IntendedUse = Literal["clothes", "kids", "linen", "mixed"]


@dataclass(frozen=True)
class Line:
    text: str
    bold: bool = False
    indent: int = 0
    warning: bool = False


@dataclass(frozen=True)
class Section:
    title: str
    lines: list[Line]


@dataclass(frozen=True)
class SpecContent:
    language: Language
    title: str
    meta: str
    prepared_for: str | None
    disclaimer: str
    disclaimer_short: str
    sections: list[Section]
    image_caption: str
    footer_page: str  # "{page}" / "{pages}" placeholders

    def texts(self) -> list[str]:
        """Every text in the document (for checks such as the production-claim guard)."""
        out = [self.title, self.meta, self.disclaimer, self.disclaimer_short, self.image_caption]
        out += [self.prepared_for] if self.prepared_for else []
        for section in self.sections:
            out.append(section.title)
            out += [line.text for line in section.lines]
        return out


@dataclass(frozen=True)
class Preferences:
    intended_use: IntendedUse | None = None
    location: str | None = None
    timeline: str | None = None
    requests: str | None = None
    name: str | None = None  # shown on the PDF only if the customer typed it


# ASSUMPTION: Hebrew names for the catalog (the catalog itself is English only).
CATALOG_HE = {
    "melamine": "מלמין", "oak_veneer": "פורניר אלון", "lacquered_mdf": "MDF בגימור לכה",
    "white": "לבן", "light_grey": "אפור בהיר", "anthracite": "אנתרציט", "black": "שחור",
    "natural_oak": "אלון טבעי", "walnut": "אגוז",
    "matte": "מט", "satin": "סאטן", "gloss": "מבריק",
}

T: dict[Language, dict[str, str]] = {
    "he": {
        "title": "סיכום עיצוב ארון",
        "meta": "תאריך: {date} · גרסת עיצוב: {revision}",
        "prepared_for": "הוכן עבור: {name}",
        "disclaimer": "טיוטת עיצוב חזותית בלבד, לא שרטוט ייצור. המידות מוצגות כפי שתוכננו באפליקציה, "
                      "ועל הנגר לאמת את כל המידות במקום לפני כל עבודה.",
        "disclaimer_short": "טיוטת עיצוב חזותית, לא שרטוט ייצור. יש לאמת את כל המידות במקום.",
        "page": "עמוד {page} מתוך {pages}",
        "cm": 'ס"מ',
        "overall": "מידות כלליות",
        "outer": 'רוחב {w} ס"מ · גובה {h} ס"מ · עומק {d} ס"מ',
        "inner": 'מידות פנים: רוחב {w} ס"מ · גובה {h} ס"מ',
        "panel": 'עובי לוחות הגוף: {t} ס"מ',
        "layout": "{n} תאים · {p} מחיצות",
        "compartments": "תאים (משמאל לימין)",
        "heights_note": "הגבהים נמדדים מהחלק העליון של לוח הבסיס.",
        "compartment": 'תא {i} · רוחב {w} ס"מ',
        "drawer": 'מגירה: {y0}–{y1} ס"מ',
        "shelf": 'מדף בגובה {y} ס"מ',
        "rail": 'מוט תלייה בגובה {y} ס"מ (מתחתיו {free} ס"מ פנויים)',
        "empty": "ללא פריטים",
        "own_finish": "{item} · {appearance}",
        "doors": "דלתות",
        "hinged": "דלתות ציר · {n} דלתות",
        "door": "דלת {k}: {compartments} · {hinge}",
        "door_compartments": "תאים {list}",
        "door_compartment": "תא {list}",
        "hinge_left": "ציר בצד שמאל",
        "hinge_right": "ציר בצד ימין",
        "sliding": "דלתות הזזה · {n} כנפיים",
        "no_doors": "ללא דלתות",
        "materials": "חומרים, צבעים וגימורים",
        "carcass_look": "גוף, מדפים ומגירות: {appearance}",
        "doors_look": "דלתות: {appearance}",
        "appearance": "{material}, {color}, גימור {finish}",
        "warnings": "הערות מרווח",
        "warn_rail": 'תא {c}: מתחת למוט בגובה {y} ס"מ נשארים רק {free} ס"מ פנויים לתלייה.',
        "warn_shelves": 'תא {c}: בין המדפים בגובה {low} ו-{high} ס"מ נשארים רק {gap} ס"מ.',
        "no_warnings": "אין הערות.",
        "preferences": "העדפות והערות הלקוח",
        "use": "שימוש מתוכנן: {value}",
        "location": "מיקום ההתקנה: {value}",
        "timeline": "לוח זמנים: {value}",
        "requests": "בקשות מיוחדות: {value}",
        "summary": "סיכום (נכתב על ידי AI)",
        "image_caption": "תמונה להמחשה מתוך מודל התלת-ממד, לא בקנה מידה.",
    },
    "en": {
        "title": "Wardrobe design summary",
        "meta": "Date: {date} · Design revision: {revision}",
        "prepared_for": "Prepared for: {name}",
        "disclaimer": "Visual design draft only, not a manufacturing drawing. Measurements are as designed in the app; "
                      "the carpenter must verify every measurement on site before any work.",
        "disclaimer_short": "Visual design draft, not a manufacturing drawing. Verify all measurements on site.",
        "page": "Page {page} of {pages}",
        "cm": "cm",
        "overall": "Overall dimensions",
        "outer": "Width {w} cm · Height {h} cm · Depth {d} cm",
        "inner": "Interior: width {w} cm · height {h} cm",
        "panel": "Carcass panel thickness: {t} cm",
        "layout": "{n} compartments · {p} partitions",
        "compartments": "Compartments (left to right)",
        "heights_note": "Heights are measured from the top of the bottom panel.",
        "compartment": "Compartment {i} · width {w} cm",
        "drawer": "Drawer: {y0}–{y1} cm",
        "shelf": "Shelf at {y} cm",
        "rail": "Hanging rail at {y} cm ({free} cm free below)",
        "empty": "No items",
        "own_finish": "{item} · {appearance}",
        "doors": "Doors",
        "hinged": "Hinged doors · {n} doors",
        "door": "Door {k}: {compartments} · {hinge}",
        "door_compartments": "compartments {list}",
        "door_compartment": "compartment {list}",
        "hinge_left": "hinged on the left",
        "hinge_right": "hinged on the right",
        "sliding": "Sliding doors · {n} panels",
        "no_doors": "No doors",
        "materials": "Materials, colours and finishes",
        "carcass_look": "Carcass, shelves and drawers: {appearance}",
        "doors_look": "Doors: {appearance}",
        "appearance": "{material}, {color}, {finish} finish",
        "warnings": "Clearance notes",
        "warn_rail": "Compartment {c}: only {free} cm is free for hanging below the rail at {y} cm.",
        "warn_shelves": "Compartment {c}: only {gap} cm between the shelves at {low} and {high} cm.",
        "no_warnings": "None.",
        "preferences": "Customer preferences and notes",
        "use": "Intended use: {value}",
        "location": "Installation location: {value}",
        "timeline": "Timeline: {value}",
        "requests": "Special requests: {value}",
        "summary": "Summary (written by AI)",
        "image_caption": "Illustrative image from the 3D model; not to scale.",
    },
}

USES: dict[Language, dict[str, str]] = {
    "he": {"clothes": "בגדים", "kids": "חדר ילדים", "linen": "מצעים ומגבות", "mixed": "משולב"},
    "en": {"clothes": "Clothes", "kids": "Kids' room", "linen": "Linen and towels", "mixed": "Mixed"},
}


def _name(ref: dict, catalog_names: dict[str, str], language: Language) -> str:
    if ref.get("custom"):
        return f"{ref['name']} ({ref['hex']})" if ref.get("hex") else ref["name"]
    catalog_id = ref["catalogId"]
    if language == "he" and catalog_id in CATALOG_HE:
        return CATALOG_HE[catalog_id]
    return catalog_names.get(catalog_id, catalog_id)


def _appearance(appearance: dict, catalog_names: dict[str, str], t: dict[str, str], language: Language) -> str:
    return t["appearance"].format(
        material=_name(appearance["material"], catalog_names, language),
        color=_name(appearance["color"], catalog_names, language),
        finish=_name(appearance["finish"], catalog_names, language),
    )


def _compartment_lines(compartment: dict, index: int, catalog_names: dict[str, str], t: dict[str, str],
                       language: Language, rail_free: dict[str, int]) -> list[Line]:
    items: list[tuple[int, str, dict | None]] = []
    for drawer in compartment["drawers"]:
        items.append((drawer["y"], t["drawer"].format(y0=cm(drawer["y"]), y1=cm(drawer["y"] + drawer["height"])), drawer.get("appearance")))
    for shelf in compartment["shelves"]:
        items.append((shelf["y"], t["shelf"].format(y=cm(shelf["y"])), shelf.get("appearance")))
    for rail in compartment["rails"]:
        items.append((rail["y"], t["rail"].format(y=cm(rail["y"]), free=cm(rail_free[rail["id"]])), None))
    lines = [Line(t["compartment"].format(i=index, w=cm(compartment["width"])), bold=True)]
    for _, text, appearance in sorted(items, key=lambda item: item[0]):
        if appearance:
            text = t["own_finish"].format(item=text, appearance=_appearance(appearance, catalog_names, t, language))
        lines.append(Line(text, indent=1))
    if not items:
        lines.append(Line(t["empty"], indent=1))
    return lines


def _door_lines(doors: dict, compartment_index: dict[str, int], t: dict[str, str]) -> list[Line]:
    if doors["type"] == "none" or not doors["items"]:
        return [Line(t["no_doors"])]
    if doors["type"] == "sliding":
        return [Line(t["sliding"].format(n=len(doors["items"])))]
    lines = [Line(t["hinged"].format(n=len(doors["items"])))]
    for k, door in enumerate(doors["items"], start=1):
        numbers = sorted(compartment_index[c] for c in door["compartmentIds"])
        key = "door_compartments" if len(numbers) > 1 else "door_compartment"
        hinge = t["hinge_left"] if door.get("hingeSide") == "left" else t["hinge_right"]
        lines.append(Line(t["door"].format(k=k, compartments=t[key].format(list=", ".join(map(str, numbers))), hinge=hinge), indent=1))
    return lines


def build_content(design: dict, catalog: dict, *, revision: int, language: Language, preferences: Preferences,
                  summary: str | None, today: date) -> SpecContent:
    """`design` must already be validated (the engine's canonical form)."""
    t = T[language]
    catalog_names = {item["id"]: item["name"] for kind in ("materials", "colors", "finishes") for item in catalog[kind]}
    dims = design["dimensions"]
    compartments = design["compartments"]
    compartment_index = {c["id"]: i for i, c in enumerate(compartments, start=1)}
    issues = design_issues(design)
    rail_free = {rail["id"]: free_below(c, rail["y"]) for c in compartments for rail in c["rails"]}

    sections = [
        Section(t["overall"], [
            Line(t["outer"].format(w=cm(dims["width"]), h=cm(dims["height"]), d=cm(dims["depth"])), bold=True),
            Line(t["inner"].format(w=cm(interior_width(design)), h=cm(interior_height(design)))),
            Line(t["panel"].format(t=cm(design["carcass"]["panelThickness"]))),
            Line(t["layout"].format(n=len(compartments), p=len(design["partitions"]))),
        ]),
        Section(t["compartments"], [Line(t["heights_note"])] + [
            line for i, c in enumerate(compartments, start=1)
            for line in _compartment_lines(c, i, catalog_names, t, language, rail_free)
        ]),
        Section(t["doors"], _door_lines(design["doors"], compartment_index, t)),
        Section(t["materials"], [
            Line(t["carcass_look"].format(appearance=_appearance(design["carcass"]["appearance"], catalog_names, t, language))),
            *([Line(t["doors_look"].format(appearance=_appearance(design["doors"]["appearance"], catalog_names, t, language)))]
              if design["doors"]["type"] != "none" else []),
        ]),
        Section(t["warnings"], [
            Line(t["warn_rail"].format(c=i["compartment"], y=cm(i["y"]), free=cm(i["free"])), warning=True) if i["kind"] == "rail"
            else Line(t["warn_shelves"].format(c=i["compartment"], low=cm(i["low"]), high=cm(i["high"]), gap=cm(i["gap"])), warning=True)
            for i in issues
        ] or [Line(t["no_warnings"])]),
    ]
    preference_lines = [
        Line(t[key].format(value=value)) for key, value in (
            ("use", USES[language][preferences.intended_use] if preferences.intended_use else None),
            ("location", preferences.location), ("timeline", preferences.timeline), ("requests", preferences.requests),
        ) if value
    ]
    if preference_lines:
        sections.append(Section(t["preferences"], preference_lines))
    if summary:
        sections.append(Section(t["summary"], [Line(summary)]))

    return SpecContent(
        language=language,
        title=t["title"],
        meta=t["meta"].format(date=today.strftime("%d.%m.%Y"), revision=revision),
        prepared_for=t["prepared_for"].format(name=preferences.name) if preferences.name else None,
        disclaimer=t["disclaimer"],
        disclaimer_short=t["disclaimer_short"],
        sections=sections,
        image_caption=t["image_caption"],
        footer_page=t["page"],
    )

