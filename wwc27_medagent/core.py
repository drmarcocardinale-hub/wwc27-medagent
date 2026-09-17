"""Pure, testable functions behind the WWC27-MedAgent MCP tools.

Everything here is deterministic and traceable to the data files in ./data.
No player-identifiable data is accepted, stored or transmitted.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from functools import lru_cache
from importlib import resources
from typing import Any

__version__ = "0.1.0"

DISCLAIMER = (
    "Decision support only. Outputs summarise published evidence and climate normals; "
    "they do not replace clinical judgement, on-site environmental measurement or "
    "current public-health advice."
)

OUT_OF_SCOPE = (
    "I don't know: this question is outside the WWC27-MedAgent evidence base. "
    "No source in the curated evidence table supports an answer."
)


# --------------------------------------------------------------------------- data
@lru_cache(maxsize=None)
def _load(name: str) -> Any:
    with resources.files("wwc27_medagent.data").joinpath(name).open(encoding="utf-8") as fh:
        return json.load(fh)


def venues() -> dict:
    return _load("venues.json")["venues"]


def tournament() -> dict:
    return _load("venues.json")["tournament"]


def references() -> dict:
    return _load("references.json")


def evidence() -> list[dict]:
    return _load("evidence.json")


def screening_matrix() -> dict:
    return _load("screening.json")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def resolve_venue(name: str) -> str:
    """Map a free-text city or stadium name to a venue key."""
    key = _norm(name)
    v = venues()
    if key in v:
        return key
    for k, rec in v.items():
        if key in (_norm(rec["city"]), _norm(rec["stadium"])) or key in _norm(rec["stadium"]):
            return k
    aliases = {"rio": "rio_de_janeiro", "maracana": "rio_de_janeiro", "sp": "sao_paulo",
               "bh": "belo_horizonte", "poa": "porto_alegre", "brasilia_df": "brasilia"}
    if key in aliases:
        return aliases[key]
    raise ValueError(f"Unknown host city or stadium: {name!r}. Valid: {', '.join(v)}")


def cite(ref_key: str) -> dict:
    r = references()[ref_key]
    link = f"https://doi.org/{r['doi']}" if r.get("doi") else r.get("url")
    return {"key": ref_key, "citation": r["cite"], "link": link}


# ------------------------------------------------------------------ environment
def simplified_wbgt(temp_c: float, rh_pct: float) -> float:
    """Australian Bureau of Meteorology simplified WBGT (sWBGT).

    sWBGT = 0.567*T + 0.393*e + 3.94, with e the vapour pressure (hPa).
    It ignores solar radiation and wind, so it is indicative only.
    """
    if not (-40 <= temp_c <= 60) or not (0 <= rh_pct <= 100):
        raise ValueError("temperature or humidity out of physical range")
    e = rh_pct / 100 * 6.105 * math.exp(17.27 * temp_c / (237.7 + temp_c))
    return round(0.567 * temp_c + 0.393 * e + 3.94, 1)


def heat_band(wbgt: float) -> dict:
    """Reference bands from FIFA (historical) and FIFPRO policy positions."""
    if wbgt > 32:
        band = "very high"
        action = ("Above FIFA's historical 32 °C mandatory cooling-break threshold; "
                  "FIFPRO recommends rescheduling training/matches.")
    elif wbgt >= 28:
        band = "high"
        action = "FIFPRO recommends cooling breaks (~30th and ~75th minute); full heat plan."
    elif wbgt >= 23:
        band = "moderate"
        action = ("Individual cooling and hydration plans; monitor heat-susceptible players. "
                  "(23-28 °C band is an author-defined planning band, not a policy threshold.)")
    else:
        band = "low"
        action = "Standard hydration; consider cold/wet-weather warm-up if temperatures are low."
    return {"band": band, "action": action, "source": cite("FIFPRO"),
            "thresholds": "FIFA historical: >32 °C mandatory cooling breaks; FIFPRO: 28-32 °C cooling "
                          "breaks, >32 °C reschedule."}


def venue_profile(city: str, month: str = "both") -> dict:
    key = resolve_venue(city)
    rec = venues()[key]
    months = ["june", "july"] if month == "both" else [month.lower()]
    out: dict[str, Any] = {
        "venue_key": key, "city": rec["city"], "stadium": rec["stadium"],
        "elevation_m": rec["elevation_m"], "climate_group": rec["climate_group"],
        "climate_normals_period": rec["normals"],
        "yellow_fever_vaccine_cdc_2026": rec["yellow_fever_vaccine_cdc_2026"],
        "months": {},
    }
    for m in months:
        c = rec[m]
        w_mean = simplified_wbgt(c["tmean"], c["rh"])
        w_max = simplified_wbgt(c["tmax"], c["rh"])
        out["months"][m] = {**c, "indicative_swbgt_mean_c": w_mean, "indicative_swbgt_max_c": w_max,
                            "heat_band_at_daily_max": heat_band(w_max)["band"]}
    out["sources"] = [cite("INMET"), cite("CDC2026")]
    out["disclaimer"] = DISCLAIMER + " sWBGT from monthly means with mean humidity overstates " \
        "afternoon humidity and ignores sun and wind."
    return out


def heat_risk(temp_c: float, rh_pct: float, luteal_phase: bool = False) -> dict:
    w = simplified_wbgt(temp_c, rh_pct)
    res = {"indicative_swbgt_c": w, **heat_band(w)}
    if luteal_phase:
        res["female_physiology_note"] = {
            "note": "Core temperature is higher in the luteal phase at rest and after exercise; "
                    "consider earlier/extra cooling.",
            "source": cite("Giersch2020")}
    res["cooling_evidence"] = cite("Convit2024")
    res["disclaimer"] = DISCLAIMER
    return res


def distance_km(a: str, b: str) -> float:
    va, vb = venues()[resolve_venue(a)], venues()[resolve_venue(b)]
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (va["lat"], va["lon"], vb["lat"], vb["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 0)


def travel_burden(itinerary: list[str]) -> dict:
    """Great-circle legs for an ordered list of venues (base camp first if desired)."""
    if len(itinerary) < 2:
        raise ValueError("Provide at least two locations")
    keys = [resolve_venue(x) for x in itinerary]
    legs = []
    for a, b in zip(keys, keys[1:]):
        legs.append({"from": venues()[a]["city"], "to": venues()[b]["city"], "km": distance_km(a, b),
                     "climate_change": f"{venues()[a]['climate_group']} -> {venues()[b]['climate_group']}"})
    total = sum(l["km"] for l in legs)
    groups = {venues()[k]["climate_group"] for k in keys}
    return {
        "legs": legs, "total_km": total,
        "climate_groups_visited": sorted(groups),
        "flags": ([
            "Itinerary crosses contrasting climate groups: plan both heat mitigation and cold/wet routines."
        ] if len(groups) > 1 else []),
        "note": "All host cities are in UTC-3; in-tournament travel adds fatigue but no time-zone shift.",
        "sources": [cite("JanseVanRensburg2021"), cite("Esh2026")],
        "disclaimer": DISCLAIMER,
    }


# ------------------------------------------------------------------ screening
def screening_checklist(phase: str = "all", domains: list[str] | None = None,
                        venues_played: list[str] | None = None) -> dict:
    m = screening_matrix()
    phases = list(m["_meta"]["phases"]) if phase == "all" else [phase]
    for p in phases:
        if p not in m["_meta"]["phases"]:
            raise ValueError(f"Unknown phase {p!r}; use one of {list(m['_meta']['phases'])} or 'all'")
    doms = domains or list(m["domains"])
    unknown = [d for d in doms if d not in m["domains"]]
    if unknown:
        raise ValueError(f"Unknown domain(s) {unknown}; valid: {list(m['domains'])}")
    out: dict[str, Any] = {"phases": {p: m["_meta"]["phases"][p] for p in phases}, "items": {}}
    for d in doms:
        rec = m["domains"][d]
        out["items"][d] = {"label": rec["label"], **{p: rec[p] for p in phases},
                           "sources": [cite(r) for r in rec["refs"]]}
    if venues_played:
        prof = [venue_profile(v) for v in venues_played]
        hot = [p["city"] for p in prof
               if max(mm["indicative_swbgt_max_c"] for mm in p["months"].values()) >= 28]
        cool = [p["city"] for p in prof if p["climate_group"] == "cool"]
        yf = [f"{p['city']}: {p['yellow_fever_vaccine_cdc_2026']}" for p in prof]
        out["venue_specific"] = {
            "heat_exposed_venues": hot, "cool_venues": cool, "yellow_fever_by_venue": yf,
            "actions": ([f"Heat acclimation and cooling plan for {', '.join(hot)}."] if hot else [])
                       + ([f"Cold/wet warm-up and recovery plan for {', '.join(cool)}."] if cool else []),
        }
    out["disclaimer"] = DISCLAIMER
    return out


# ------------------------------------------------------------------ evidence
_STOP = {"the", "a", "an", "of", "in", "at", "and", "or", "for", "to", "what", "which", "who", "is", "are",
         "how", "does", "do", "did", "was", "were", "with", "on", "about", "by", "from", "be", "will", "should",
         "we", "our", "us", "me", "my", "give", "tell", "much", "many", "most", "per", "this", "that", "it"}
# Generic context words: they cannot, on their own, make a question answerable.
_GENERIC = {"world", "cup", "fifa", "women", "womens", "woman", "female", "females", "men", "mens",
            "team", "teams", "match", "matches", "player", "players", "tournament", "squad", "2027",
            "brazil", "elite", "football", "soccer", "time", "current", "day", "days"}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+]+", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()))


def find_evidence(query: str, domain: str | None = None, limit: int = 5) -> dict:
    """Keyword retrieval over the curated evidence table. Returns only sourced items.

    Whole-word matching; generic context words do not count; a year named in the query
    (other than 2027) must appear in the evidence item's setting, claim or keywords."""
    q = _words(query)
    is_year = lambda t: re.fullmatch(r"(19|20)\d\d", t) is not None
    terms = [t for t in q if t not in _STOP and t not in _GENERIC and len(t) > 1 and not is_year(t)]
    years = {t for t in q if is_year(t) and t != "2027"}
    scored = []
    for e in evidence():
        if domain and e["domain"] != domain:
            continue
        kw = _words(" ".join(e["keywords"]))
        hay = _words(" ".join([e["claim"], e["setting"], e["domain"].replace("_", " ")])) | kw
        if years and not years <= hay:
            continue
        matched = [t for t in terms if t in hay]
        score = sum(2 if t in kw else 1 for t in matched)
        if score >= 2 and (len(matched) >= 2 or len(terms) <= 2):
            scored.append((score, e))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    hits = [{"id": e["id"], "setting": e["setting"], "claim": e["claim"], "values": e["values"],
             "source": cite(e["ref"])} for _, e in scored[:limit]]
    if not hits:
        return {"answer": OUT_OF_SCOPE, "hits": []}
    return {"hits": hits, "disclaimer": DISCLAIMER}
