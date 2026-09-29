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
