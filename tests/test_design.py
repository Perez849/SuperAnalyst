"""The reports and the library share one design sheet (Reloj de inversión tokens)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from equityval import design, theme

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "assets", "fonts")


def test_tokens_match_the_reloj_design():
    t = theme.TOKENS
    assert t["paper"] == "#F6F2E8" and t["ink"] == "#1B1810" and t["accent"] == "#A9752C"
    assert (t["rec"], t["over"], t["stag"], t["refl"]) == ("#3F6B52", "#B8863B", "#9C4A3C", "#3E4E7A")


def test_every_declared_font_file_exists():
    for _, _, _, file in design._FONTS:
        assert os.path.exists(os.path.join(FONTS, file + ".woff2")), file


def test_css_has_no_unresolved_variables():
    css = design.css("fonts/")
    defined = set(re.findall(r"--([a-z0-9-]+):", css))
    used = set(re.findall(r"var\(--([a-z0-9-]+)\)", css))
    assert used <= defined, used - defined


def test_embedded_fonts_are_self_contained():
    css = design.css("embed")
    assert "data:font/woff2;base64," in css and "url(\"fonts/" not in css
