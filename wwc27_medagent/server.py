"""WWC27-MedAgent: an MCP server that turns the Current Opinion article
"Sports Medicine and Science Considerations to Maximise Preparation for the FIFA Women's World Cup
Brazil 2027: From Static Evidence to a Living Agent" into queryable tools, resources and prompts,
following the Paper2Agent model (Miao et al., Nature 2026).

Run locally:   python -m wwc27_medagent.server            (stdio)
Run remotely:  python -m wwc27_medagent.server --http     (streamable HTTP on :8000)
"""
from __future__ import annotations

import json
import os
import sys
from importlib import resources as ir

from mcp.server.fastmcp import FastMCP

from . import core

mcp = FastMCP(
    "wwc27-medagent",
    instructions=(
        "You are the paper agent for a Sports Medicine Current Opinion on medical screening and "
        "monitoring for the FIFA Women's World Cup Brazil 2027. Answer ONLY from the tools and "
        "resources provided. Always report the source link returned by each tool. If a tool returns "
        "'I don't know', say so rather than answering from general knowledge. Never request or store "
        "identifiable player data. Outputs are decision support for qualified clinicians."
    ),
)


# ------------------------------------------------------------------ tools
@mcp.tool()
def get_venue_profile(city: str, month: str = "both") -> dict:
    """Climate normals, elevation, indicative simplified WBGT and yellow-fever guidance for a
    Brazil 2027 host city. `city` accepts city or stadium name; `month` is 'june', 'july' or 'both'."""
    return core.venue_profile(city, month)


@mcp.tool()
def estimate_heat_risk(temperature_c: float, relative_humidity_pct: float,
                       luteal_phase: bool = False) -> dict:
    """Indicative simplified WBGT and FIFA/FIFPRO reference band for given conditions
    (e.g. a forecast for kick-off). Set luteal_phase=True to add female-physiology notes."""
    return core.heat_risk(temperature_c, relative_humidity_pct, luteal_phase)


@mcp.tool()
def calculate_travel_burden(itinerary: list[str]) -> dict:
    """Great-circle distances and climate transitions for an ordered list of host cities
    (e.g. base camp then fixtures)."""
    return core.travel_burden(itinerary)


@mcp.tool()
def build_screening_checklist(phase: str = "all", domains: list[str] | None = None,
                              venues_played: list[str] | None = None) -> dict:
    """Phase x domain screening/monitoring checklist (Table 2).
    phase: pre_tournament | preparation_camp | in_tournament | post_tournament | all.
    domains: any of cardiovascular, musculoskeletal, energy_iron, menstrual_female_health,
    heat_environment, infection_vaccination, mental_health, concussion, travel_sleep, medication.
    venues_played: optional host cities to add venue-specific actions."""
    return core.screening_checklist(phase, domains, venues_played)


@mcp.tool()
def find_evidence(query: str, domain: str | None = None, limit: int = 5) -> dict:
    """Search the curated, source-linked evidence table. Returns 'I don't know' when no
    curated source supports an answer."""
    return core.find_evidence(query, domain, limit)


@mcp.tool()
def get_air_quality(city: str, live: bool = False) -> dict:
    """Air-quality context for a host city: typical pollution sources, the June-July pattern, the
    state monitoring agency, WHO 2021 guideline levels and Brazil's national standards. Set live=True
    to add current pollutant concentrations from the Open-Meteo (CAMS) air-quality API; this needs
    internet access on the machine running the server and says so clearly when unavailable."""
    return core.air_quality(city, live)


@mcp.tool()
def plan_respiratory_care(pm2_5_ug_m3: float | None = None, athlete_has_asthma_or_eib: bool = False,
                          city: str | None = None) -> dict:
    """Airway-health planning: a PM2.5 planning band with actions (if a concentration is given),
    asthma/exercise-induced bronchoconstriction screening and management points, and the 2026
    anti-doping limits for inhaled beta-2 agonists. Do not pass identifiable player data."""
    return core.respiratory_plan(pm2_5_ug_m3, athlete_has_asthma_or_eib, city)


@mcp.tool()
def tournament_facts() -> dict:
    """Key dates and format of the FIFA Women's World Cup Brazil 2027."""
    return {**core.tournament(), "source": core.cite("FIFA2027")}


# ------------------------------------------------------------------ resources
def _text(name: str) -> str:
    return ir.files("wwc27_medagent.data").joinpath(name).read_text(encoding="utf-8")


@mcp.resource("wwc27://manuscript")
def manuscript() -> str:
    """Full text of the Current Opinion manuscript (current version)."""
    return _text("manuscript.md")


@mcp.resource("wwc27://table1-venues")
def table1() -> str:
    """Table 1 source data: host-city climate, elevation and travel-health data (JSON)."""
    return _text("venues.json")


@mcp.resource("wwc27://table2-screening")
def table2() -> str:
    """Table 2 source data: phase x domain screening and monitoring matrix (JSON)."""
    return _text("screening.json")


@mcp.resource("wwc27://air-quality")
def air_quality_resource() -> str:
    """Air-quality profiles, guideline levels, planning bands and asthma/EIB reference data (JSON)."""
    return _text("air_quality.json")


@mcp.resource("wwc27://evidence")
def evidence_table() -> str:
    """Versioned evidence table: each claim, its values and its source (JSON)."""
    return json.dumps(core.evidence(), indent=1, ensure_ascii=False)


@mcp.resource("wwc27://references")
def refs() -> str:
    """Reference list with DOIs/URLs (JSON)."""
    return _text("references.json")


@mcp.resource("wwc27://changelog")
def changelog() -> str:
    """Curation log: what changed in each version and why."""
    return _text("CHANGELOG.md")


# ------------------------------------------------------------------ prompts
@mcp.prompt()
def pre_tournament_medical_plan(base_camp: str, fixtures: str, squad_notes: str = "") -> str:
    """Workflow: draft a pre-tournament medical plan for clinician review.
    fixtures: comma-separated host cities in order. squad_notes: non-identifiable context only."""
    return f"""Draft a pre-tournament medical screening and monitoring plan for a team at the FIFA
Women's World Cup Brazil 2027. Follow these steps in order and cite every source link returned.

1. Call tournament_facts.
2. For the base camp ({base_camp}) and each fixture city ({fixtures}), call get_venue_profile.
3. Call calculate_travel_burden with [{base_camp}, {fixtures}].
4. Call build_screening_checklist with phase='all' and venues_played set to the fixture cities.
4b. Call get_air_quality for each fixture city, and plan_respiratory_care if the squad includes
   athletes with asthma or exercise-induced bronchoconstriction.
5. For any domain where the squad context suggests extra risk ({squad_notes or 'none given'}),
   call find_evidence with a focused query.
6. Write the plan as: (a) venue risk summary table; (b) actions by phase; (c) open questions for
   the medical team; (d) sources. State clearly that sWBGT values are indicative and that
   on-site WBGT, current outbreak bulletins and vaccination guidance must be checked.
Do not invent numbers or sources. If a tool says it does not know, report that gap."""


@mcp.prompt()
def venue_briefing(city: str) -> str:
    """Workflow: one-page medical briefing for a single host city."""
    return (f"Call get_venue_profile and get_air_quality for {city} (both months), then find_evidence for 'heat cooling women' "
            f"and 'infection vaccination brazil'. Summarise climate, heat band, air quality, travel-health points and "
            f"recommended actions in under 250 words with source links.")


def main() -> None:
    if "--http" in sys.argv:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = int(os.environ.get("PORT", "8000"))
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
