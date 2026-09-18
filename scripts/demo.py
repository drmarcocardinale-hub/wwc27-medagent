"""Run a realistic scenario through every tool and print the answers.

No API keys, no MCP client, no network: this exercises the agent's own evidence base and
computations so you can see what it returns before wiring it into an AI assistant.

    python scripts/demo.py                       # the default scenario
    python scripts/demo.py --base "Rio de Janeiro" --fixtures Salvador,Brasilia
    python scripts/demo.py --ask "heat cooling women"

The scenario is a team based in Sao Paulo with fixtures in Fortaleza, Recife and Porto Alegre:
the longest plausible travel burden in the tournament, crossing from cool to warm-humid and back.
"""
from __future__ import annotations

import argparse
import textwrap

from wwc27_medagent import core

W = 78


def head(n: str) -> None:
    print(f"\n{'=' * W}\n{n}\n{'=' * W}")


def wrap(text: str, indent: str = "  ") -> str:
    return textwrap.fill(str(text), W - len(indent), initial_indent=indent,
                         subsequent_indent=indent)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="Sao Paulo")
    ap.add_argument("--fixtures", default="Fortaleza,Recife,Porto Alegre")
    ap.add_argument("--ask", default="", help="run one evidence question and exit")
    a = ap.parse_args()

    if a.ask:
        head(f"find_evidence({a.ask!r})")
        r = core.find_evidence(a.ask)
        if not r.get("hits"):
            print(wrap(r.get("answer", "no hits")))
            return 0
        for h in r["hits"]:
            print(f"\n  [{h.get('id')}] {h.get('domain', '')}")
            print(wrap(h.get("claim", ""), "      "))
        return 0

    fixtures = [c.strip() for c in a.fixtures.split(",") if c.strip()]
    itinerary = [a.base] + fixtures

    head(f"TOURNAMENT  ·  base {a.base}  ·  fixtures {', '.join(fixtures)}")
    t = core.tournament()
    print(wrap(f"{t.get('name', '')}: {t.get('start', '')} to {t.get('final', t.get('semi_finals', ''))}"))

    head("1. VENUE PROFILES  (get_venue_profile)")
    print(f"  {'City':<16}{'June sWBGT':>12}{'Band at daily max':>22}{'Yellow fever':>24}")
    print("  " + "-" * (W - 4))
    for city in itinerary:
        p = core.venue_profile(city, "june")
        m = p["months"]["june"]
        print(f"  {p['city']:<16}{m['indicative_swbgt_mean_c']:>12}"
              f"{m['heat_band_at_daily_max']:>22}{p['yellow_fever_vaccine_cdc_2026'][:22]:>24}")

    head("2. TRAVEL BURDEN  (calculate_travel_burden)")
    tb = core.travel_burden(itinerary)
    for leg in tb["legs"]:
        print(f"  {leg['from']:<16} -> {leg['to']:<16}{leg['km']:>9,.0f} km   {leg['climate_change']}")
    print(f"\n  {'TOTAL':<16}{'':<20}{tb['total_km']:>9,.0f} km")

    head("3. HEAT RISK AT KICK-OFF  (estimate_heat_risk)")
    for temp, rh, luteal in [(28, 85, True), (32, 60, False), (22, 70, False)]:
        h = core.heat_risk(temp, rh, luteal)
        tag = " (luteal)" if luteal else ""
        print(f"\n  {temp} °C / {rh}% RH{tag}  ->  sWBGT {h['indicative_swbgt_c']} °C"
              f"  [{h['band'].upper()}]")
        print(wrap(h["action"], "      "))

    head("4. AIR QUALITY AND WHERE TO GET IT  (get_air_quality, list_air_quality_sources)")
    for city in itinerary:
        aq = core.air_quality(city)
        cov = aq.get("station_coverage") or {}
        print(f"\n  {aq['city']}")
        print(wrap(aq["june_july_note"], "      "))
        print(f"      open stations: {cov.get('openaq_stations', '?')}"
              f" | current PM2.5: {'yes' if cov.get('openaq_current_pm25') else 'NO'}"
              f" | grade: {cov.get('grade', '?')}")
        best = (aq.get("where_to_get_data") or [])[:2]
        print("      use: " + "; ".join(f"{b['source']} ({'auto' if b['automated'] else 'manual'})"
                                        for b in best))

    head("5. RESPIRATORY PLANNING  (plan_respiratory_care)")
    rp = core.respiratory_plan(pm2_5_ug_m3=38.0, athlete_has_asthma_or_eib=True)
    band = rp.get("pollution_band") or {}
    print(f"  PM2.5 38 µg/m³ -> band: {band.get('band', '?')}")
    print(wrap(band.get("action", band.get("advice", "")), "      "))
    print("\n  Screening:")
    for x in rp.get("screening", [])[:2]:
        print(wrap("· " + x, "      "))
    print("\n  Anti-doping limits, inhaled beta-2 agonists (2026):")
    ad = rp.get("anti_doping_2026") or {}
    for k, v in list(ad.items())[:4]:
        print(wrap(f"{k}: {v}", "      "))

    head("6. SCREENING CHECKLIST  (build_screening_checklist)")
    cl = core.screening_checklist(phase="pre_tournament")
    items = cl.get("items") or {}
    n = sum(len(d.get("pre_tournament", [])) for d in items.values())
    print(f"  {n} pre-tournament actions across {len(items)} domains")
    for dom, d in list(items.items())[:4]:
        print(f"\n  · {d.get('label', dom)}")
        for act in d.get("pre_tournament", [])[:2]:
            print(wrap("- " + act, "      "))
    if len(items) > 4:
        print(f"\n  ... and {len(items) - 4} more domains")

    head("7. EVIDENCE RETRIEVAL AND REFUSAL  (find_evidence)")
    for q in ["illness 2023 women's world cup", "heat cooling strategies",
              "best formation for defending set pieces"]:
        r = core.find_evidence(q)
        print(f"\n  ? {q}")
        if r.get("hits"):
            h = r["hits"][0]
            print(wrap(f"[{h.get('id')}] {h.get('claim', '')}", "      "))
        else:
            print(wrap("REFUSED — " + r.get("answer", ""), "      "))

    head("DONE")
    print(wrap("Every number above comes from the curated evidence base or a documented "
               "computation, and every claim in the full tool output carries its source. "
               "The last question is deliberately out of scope: the agent must decline "
               "rather than answer from general knowledge."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
