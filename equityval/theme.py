"""Design tokens -- the "Reloj de inversión" visual system, in one place.

Taken from the Investment Clock project (github.com/Perez849/reloj-inversion): editorial and
warm, like a private-bank research note. Cream paper, typographic ink, a single ochre accent,
and the four cycle phases as the only other colours. Hierarchy comes from type (Fraunces
for headlines, Inter for text, IBM Plex Mono for numbers and labels), not from colour; the one
dark surface is "the answer" block.

Everything visual reads from here. To re-skin the reports and the library page, edit this
file: no other module hard-codes a colour.
"""
from __future__ import annotations

TOKENS = dict(
    paper="#F6F2E8", paper_raised="#FBF9F3", paper_deep="#EEE6D2",
    ink="#1B1810", ink_2="#322C1F", ink_soft="#5B5340", ink_faint="#8C8268",
    line="rgba(27,24,16,.14)", line_soft="rgba(27,24,16,.08)", line_strong="rgba(27,24,16,.28)",
    accent="#A9752C", accent_ink="#7C5620", accent_soft="rgba(169,117,44,.12)",
    rec="#3F6B52", over="#B8863B", stag="#9C4A3C", refl="#3E4E7A",      # the four phases
    pos="#3F6B52", neg="#9C4A3C",
    gold="#D9B978",                                                      # accent on the dark block
)

FONT_SERIF = '"Fraunces","Iowan Old Style",Georgia,serif'
FONT_SANS = '"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
FONT_MONO = '"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace'

# Rating bands, on the 12-month expected total return. One definition for report, JSON, index.
RATING_BANDS = [          # (floor, label, direction)
    (0.15, "OVERWEIGHT", "up"),
    (0.05, "ADD", "up"),
    (-0.05, "NEUTRAL", "flat"),
    (-0.15, "REDUCE", "down"),
    (-9.99, "UNDERWEIGHT", "down"),
]


def rating_for(total_return: float, rated: bool = True) -> tuple[str, str]:
    if not rated:
        return "NOT RATED", "flat"
    for floor, label, direction in RATING_BANDS:
        if total_return >= floor:
            return label, direction
    return RATING_BANDS[-1][1], RATING_BANDS[-1][2]


# --- the four phases (clockwise from top-left, as on the Investment Clock) -----------------
PHASE_ORDER = ["recovery", "overheat", "stagflation", "reflation"]
PHASE_NAMES = {            # English (research notes)
    "recovery": ("Recovery", "growth ↑ · inflation ↓", "equities"),
    "overheat": ("Overheat", "growth ↑ · inflation ↑", "commodities"),
    "stagflation": ("Stagflation", "growth ↓ · inflation ↑", "cash"),
    "reflation": ("Reflation", "growth ↓ · inflation ↓", "bonds"),
}
PHASE_NAMES_ES = {         # Spanish (the web, as in the Reloj de inversión site)
    "recovery": ("Recuperación", "crecimiento ↑ · inflación ↓", "renta variable"),
    "overheat": ("Sobrecalentamiento", "crecimiento ↑ · inflación ↑", "materias primas"),
    "stagflation": ("Estanflación", "crecimiento ↓ · inflación ↑", "efectivo"),
    "reflation": ("Reflación", "crecimiento ↓ · inflación ↓", "bonos"),
}


def phase_names(lang: str = "en") -> dict:
    return PHASE_NAMES_ES if lang == "es" else PHASE_NAMES


# Classic Investment Clock sector map (illustrative): primary phase first.
SECTOR_PHASES = {
    "technology": ("recovery", "reflation"),
    "communication services": ("recovery", "reflation"),
    "consumer cyclical": ("recovery", "reflation"),
    "industrials": ("overheat", "recovery"),
    "energy": ("overheat", "stagflation"),
    "basic materials": ("overheat", "recovery"),
    "financial services": ("reflation", "recovery"),
    "real estate": ("reflation", "recovery"),
    "utilities": ("stagflation", "reflation"),
    "consumer defensive": ("stagflation", "reflation"),
    "healthcare": ("stagflation", "recovery"),
}


def phases_for(sector: str | None, profile: str | None = None) -> tuple[str, str]:
    s = (sector or "").strip().lower()
    if s in SECTOR_PHASES:
        return SECTOR_PHASES[s]
    by_profile = {"bank": ("reflation", "recovery"), "insurance": ("reflation", "recovery"),
                  "reit": ("reflation", "recovery"), "utility": ("stagflation", "reflation"),
                  "cyclical": ("overheat", "stagflation"), "high_growth": ("recovery", "reflation"),
                  "standard": ("recovery", "overheat")}
    return by_profile.get(profile or "", ("recovery", "overheat"))


def brand_mark(size: int = 30) -> str:
    """The clock-face brand mark: ink hour hand, ochre minute hand."""
    t = TOKENS
    return (f'<svg class="brand-mark" width="{size}" height="{size}" viewBox="0 0 32 32" aria-hidden="true">'
            f'<circle cx="16" cy="16" r="14.5" fill="none" stroke="{t["ink"]}" stroke-width="1.3"/>'
            f'<path d="M16 16 L16 6.5" stroke="{t["accent"]}" stroke-width="1.6" stroke-linecap="round"/>'
            f'<path d="M16 16 L23 20" stroke="{t["ink"]}" stroke-width="1.6" stroke-linecap="round"/>'
            f'<circle cx="16" cy="16" r="1.6" fill="{t["ink"]}"/></svg>')
