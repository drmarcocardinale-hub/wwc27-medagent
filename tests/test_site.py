"""The reader site must not be able to disagree with the agent.

The Try it panel looks numbers up in a grid generated here by core; if the generator ever
drifts from core, or someone re-implements the formula in JavaScript, these fail.
"""
import importlib.util
import sys
from pathlib import Path

from wwc27_medagent import core

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(_spec)
sys.modules["build_site"] = build_site
_spec.loader.exec_module(build_site)


def test_heat_grid_matches_core_in_every_cell():
    g = build_site.heat_grid()
    t0, ts = g["temp_c"]["min"], g["temp_c"]["step"]
    h0, hs = g["rh_pct"]["min"], g["rh_pct"]["step"]
    checked = 0
    for i, row in enumerate(g["swbgt"]):
        t = round(t0 + i * ts, 1)
        for j, w in enumerate(row):
            h = h0 + j * hs
            assert w == core.simplified_wbgt(t, h), f"sWBGT differs at {t} C / {h}%"
            assert g["bands"][g["band_index"][i][j]] == core.heat_band(w)["band"], \
                f"band differs at {t} C / {h}%"
            checked += 1
    assert checked > 500, "grid is suspiciously small"


def test_heat_grid_action_text_is_cores_own():
    g = build_site.heat_grid()
    assert set(g["actions"]) == set(g["bands"])
    for band, action in g["actions"].items():
        assert action.strip(), f"no action text for band {band}"
    assert g["source"]["key"] == "FIFPRO"
    assert g["package_version"] == core.__version__


def test_venue_table_bands_come_from_core():
    for row in build_site.venue_rows():
        for month in ("june", "july"):
            m = row[month]
            assert m["band"] == core.heat_band(m["swbgt_at_daily_max"])["band"]


# --------------------------------------------------------------------------- the architecture figure

def _arch():
    return build_site.ARCH_FIGURE


def test_the_figure_counts_match_what_the_server_actually_exposes():
    """The figure states "9 tools, 7 resources, 2 prompts". Those are drawn by hand, so adding a
    tool would leave a picture on a page cited in an article quietly telling readers a wrong
    number. Fail here instead."""
    import asyncio

    from wwc27_medagent.server import mcp

    counts = {
        "tools": len(asyncio.run(mcp.list_tools())),
        "resources": len(asyncio.run(mcp.list_resources())),
        "prompts": len(asyncio.run(mcp.list_prompts())),
    }
    fig = _arch()
    for label, n in counts.items():
        assert f"{n} {label}" in fig, (
            f"the figure does not say '{n} {label}'; the server exposes {n}")


def test_the_figure_names_the_data_files_that_exist():
    """Each filename in the figure must be a real file, and every data file must appear: a
    diagram of the evidence base that omits part of it is worse than no diagram."""
    from pathlib import Path as _P

    data = {p.name for p in (ROOT / "wwc27_medagent" / "data").glob("*.json")}
    fig = _arch()
    named = {n for n in data if n in fig}
    assert named == data, f"figure and data/ disagree; missing from the figure: {sorted(data - named)}"


def test_the_figure_is_self_contained_and_accessible():
    """Inline SVG on this page: no scripts, no external images, and a label for readers who
    cannot see it."""
    fig = _arch()
    for banned in ("<script", "<foreignObject", "<image", "http://", "xlink:href"):
        assert banned not in fig, f"the figure should not contain {banned}"
    assert 'role="img"' in fig and 'aria-label=' in fig
    assert "<figcaption>" in fig


# --------------------------------------------------------------------------- page structure

def _built_html():
    return (ROOT / "docs" / "index.html").read_text(encoding="utf-8")


def _parse_sections(html):
    """Return (ordered section ids, [(inner, outer) nesting faults], [unclosed ids])."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.open, self.nested, self.ids = [], [], []

        def handle_starttag(self, tag, attrs):
            if tag == "section":
                sid = dict(attrs).get("id")
                if self.open:
                    self.nested.append((sid, self.open[-1]))
                self.open.append(sid)
                self.ids.append(sid)

        def handle_endtag(self, tag):
            if tag == "section" and self.open:
                self.open.pop()

    p = P()
    p.feed(html)
    return p.ids, p.nested, p.open


def test_no_tab_section_is_nested_inside_another():
    """A missing </section> put the References panel inside the hidden "How it works" panel, so
    the tab rendered empty on the live site. Every section was still in the DOM, which is why a
    test that counted elements passed while the page was broken - nest, do not count."""
    ids, nested, unclosed = _parse_sections(_built_html())
    assert not nested, f"section(s) nested inside another: {nested}"
    assert not unclosed, f"section(s) never closed: {unclosed}"


def test_every_tab_has_a_section_and_every_section_has_a_tab():
    import re

    html = _built_html()
    tabs = set(re.findall(r'<button role="tab"[^>]*data-tab="([^"]+)"', html))
    ids = set(_parse_sections(html)[0])
    assert tabs == ids, (
        f"tabs without a panel: {sorted(tabs - ids)}; panels without a tab: {sorted(ids - tabs)}")
