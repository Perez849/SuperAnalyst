"""Design tokens -- the "Investment Clock" look, in one place.

The identity borrows from the classic Merrill Lynch Investment Clock: a dial divided into
four phases (Recovery -> Overheat -> Stagflation -> Reflation, clockwise), each with its own
colour. Screen is a dark instrument-panel; print flips to a light paper palette so PDFs do
not burn a toner cartridge.

Everything visual reads from here. To re-skin the reports / library page, edit these dicts:
no other file hard-codes a colour. Tokens are substituted into the CSS at build time (not
CSS variables) so older PDF engines such as wkhtmltopdf render them too.
"""
from __future__ import annotations

# --- screen (dark dial) ---------------------------------------------------------------------
SCREEN = dict(
    bg="#0A0F1C", surface="#101828", surface2="#16213A", ink="#E8EDF6", muted="#8C99B0",
    hair="#25324D", brass="#D9B36B", brass_dim="#8C7340",
    up="#38B887", down="#EB6757", flat="#8C99B0",
    recovery="#38B887", overheat="#F2A03D", stagflation="#A585E8", reflation="#4F94F7",
    warn_bg="#2A2417", ok_bg="#10261F", bad_bg="#2D1A1A",
    shadow="0 10px 30px rgba(0,0,0,.35)",
)

# --- print (light paper) ---------------------------------------------------------------------
PRINT = dict(
    bg="#FFFFFF", surface="#F6F4EE", surface2="#EEEBE2", ink="#10151F", muted="#566074",
    hair="#CFCBBE", brass="#8A6A2C", brass_dim="#B79B63",
    up="#1B7A5A", down="#B23A48", flat="#566074",
    recovery="#1E8E5C", overheat="#C9741A", stagflation="#7655C4", reflation="#2C6FD6",
    warn_bg="#F7EEDA", ok_bg="#E3F0E9", bad_bg="#F6E7E3",
    shadow="none",
)

FONT_SANS = '"Inter","Helvetica Neue",Arial,system-ui,-apple-system,sans-serif'
FONT_SERIF = '"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif'
FONT_MONO = 'ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace'

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


# Classic Investment Clock sector map (illustrative): primary phase first.
PHASE_ORDER = ["recovery", "overheat", "stagflation", "reflation"]     # clockwise from top-left
PHASE_NAMES = {
    "recovery": ("Recovery", "growth ↑  inflation ↓", "equities"),
    "overheat": ("Overheat", "growth ↑  inflation ↑", "commodities"),
    "stagflation": ("Stagflation", "growth ↓  inflation ↑", "cash"),
    "reflation": ("Reflation", "growth ↓  inflation ↓", "bonds"),
}
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
