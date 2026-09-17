"""Validation tests: every tool output is checked against the source values reported in the
manuscript (Paper2Agent-style 'test-verifier' step). Run with: pytest -q"""
import asyncio
import json
import re

import pytest

from wwc27_medagent import core


# ---------------------------------------------------------------- data integrity
def test_eight_venues_and_tournament_dates():
    assert len(core.venues()) == 8
    t = core.tournament()
    assert t["start"] == "2027-06-24" and t["final"].startswith("2027-07-25")
    assert t["teams"] == 32 and t["matches"] == 64


def test_every_evidence_item_has_resolvable_source():
    refs = core.references()
    ids = [e["id"] for e in core.evidence()]
    assert len(ids) == len(set(ids))
    for e in core.evidence():
        assert e["ref"] in refs, e["id"]
        c = core.cite(e["ref"])
        assert c["link"] and c["link"].startswith("https://"), e["id"]


def test_screening_refs_resolve():
    refs = core.references()
    for d, rec in core.screening_matrix()["domains"].items():
        for r in rec["refs"]:
            assert r in refs, (d, r)


def test_dois_are_well_formed():
    for k, r in core.references().items():
        if "doi" in r:
            assert re.match(r"^10\.\d{4,9}/\S+$", r["doi"]), k


# ---------------------------------------------------------------- source values
@pytest.mark.parametrize("city,month,field,value", [
    ("Fortaleza", "july", "tmax", 30.6),
    ("Fortaleza", "june", "rh", 79.9),
    ("Porto Alegre", "july", "tmean", 14.1),
    ("Brasilia", "july", "rh", 51.0),
    ("Recife", "june", "precip_mm", 390.5),
    ("Maracana", "june", "tmax", 26.7),
])
def test_climate_normals_match_source(city, month, field, value):
    assert core.venue_profile(city)["months"][month][field] == value


def test_elevations():
    assert core.venue_profile("Brasília")["elevation_m"] == 1172
    assert core.venue_profile("Belo Horizonte")["elevation_m"] == 852


def test_evidence_values_match_manuscript():
    ev = {e["id"]: e for e in core.evidence()}
    assert ev["E05"]["values"]["overall"] == 5.6 and ev["E05"]["values"]["match"] == 20.6
    assert ev["E06"]["values"]["respiratory_pct"] == 80
    assert ev["E10"]["values"]["overall"] == 5.2 and ev["E10"]["values"]["contact_pct"] == 59
    assert ev["E13"]["values"]["women_rate"] == 81.2
    assert ev["E25"]["values"]["acl_reduction_pct"] == 61
    assert ev["E26"]["values"]["major_pct"] == 0.2
    assert ev["E24"]["values"]["acl_median_days"] == 292


# ---------------------------------------------------------------- computations
def test_swbgt_known_value_and_monotonic():
    # hand-computed: T=30, RH=50 -> e=21.21 hPa -> 0.567*30+0.393*21.21+3.94 = 29.29
    assert core.simplified_wbgt(30, 50) == pytest.approx(29.3, abs=0.05)
    assert core.simplified_wbgt(30, 80) > core.simplified_wbgt(30, 50)
    with pytest.raises(ValueError):
        core.simplified_wbgt(30, 150)


def test_heat_bands_follow_policy_thresholds():
    assert core.heat_band(33)["band"] == "very high"
    assert core.heat_band(30)["band"] == "high"
    assert core.heat_band(27.9)["band"] == "moderate"
    assert core.heat_band(18)["band"] == "low"


def test_venue_contrast_is_large():
    fort = core.venue_profile("Fortaleza")["months"]["june"]["indicative_swbgt_max_c"]
    poa = core.venue_profile("Porto Alegre")["months"]["july"]["indicative_swbgt_mean_c"]
    assert poa < 20 < 30 < fort
    assert fort - poa > 15


def test_longest_leg_porto_alegre_fortaleza():
    d = core.distance_km("Porto Alegre", "Fortaleza")
    assert 3150 <= d <= 3250
    all_d = [core.distance_km(a, b) for a in core.venues() for b in core.venues() if a < b]
    assert max(all_d) == d


def test_travel_burden_flags_climate_contrast():
    tb = core.travel_burden(["Rio", "Fortaleza", "Porto Alegre"])
    assert len(tb["legs"]) == 2 and tb["flags"]


def test_luteal_note():
    r = core.heat_risk(29, 80, luteal_phase=True)
    assert "Giersch2020" == r["female_physiology_note"]["source"]["key"]


def test_yellow_fever_state_guidance():
    assert core.venue_profile("Brasilia")["yellow_fever_vaccine_cdc_2026"] == "recommended"
    assert core.venue_profile("Recife")["yellow_fever_vaccine_cdc_2026"].startswith("not recommended")


# ---------------------------------------------------------------- screening
def test_checklist_all_domains_and_venue_actions():
    cl = core.screening_checklist("all", venues_played=["Fortaleza", "Porto Alegre"])
    assert len(cl["items"]) == 10
    vs = cl["venue_specific"]
    assert "Fortaleza" in vs["heat_exposed_venues"] and "Porto Alegre" in vs["cool_venues"]


def test_checklist_rejects_bad_phase():
    with pytest.raises(ValueError):
        core.screening_checklist("halftime")


def test_unknown_city_rejected():
    with pytest.raises(ValueError):
        core.venue_profile("Manaus")


# ---------------------------------------------------------------- retrieval & refusal
@pytest.mark.parametrize("q,expected", [
    ("respiratory illness at Qatar 2022", "E06"),
    ("ACL prevention neuromuscular training", "E25"),
    ("cardiac screening female players ECG", "E26"),
    ("concussion pressure from coaches", "E18"),
    ("dengue brazil", "E28"),
    ("menstrual cycle core temperature heat", "E23"),
])
def test_find_evidence_top_hit(q, expected):
    hits = core.find_evidence(q)["hits"]
    assert hits and expected in [h["id"] for h in hits[:3]]


@pytest.mark.parametrize("q", [
    "best striker transfer fee 2027",
    "recipe for feijoada",
    "who will win the tournament",
    "stock price of adidas",
])
def test_out_of_scope_refusal(q):
    r = core.find_evidence(q)
    assert r["hits"] == [] and r["answer"].startswith("I don't know")


# ---------------------------------------------------------------- MCP server
def test_server_registers_tools_resources_prompts():
    from wwc27_medagent.server import mcp

    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"get_venue_profile", "estimate_heat_risk", "calculate_travel_burden",
            "build_screening_checklist", "find_evidence", "tournament_facts"} <= tools
    res = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    assert "wwc27://evidence" in res and "wwc27://manuscript" in res
    prompts = {p.name for p in asyncio.run(mcp.list_prompts())}
    assert "pre_tournament_medical_plan" in prompts


def test_server_tool_call_roundtrip():
    from wwc27_medagent.server import mcp

    out = asyncio.run(mcp.call_tool("get_venue_profile", {"city": "Recife", "month": "june"}))
    payload = out[1] if isinstance(out, tuple) else out
    text = json.dumps(payload, default=str)
    assert "Recife" in text and "390.5" in text
