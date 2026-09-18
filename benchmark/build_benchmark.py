"""Build the WWC27-MedAgent validation benchmark (benchmark/questions.jsonl).

Four sets, following the Paper2Agent evaluation design (Miao et al., Nature 2026):
  A  reproduction      (25) - single facts reported in the article/sources; exact ground truth
  B  application       (13) - novel questions that need tool computation or composition
  C  open-ended        (11) - practitioner scenarios scored by two raters with a rubric
  D  out-of-scope      (12) - questions the evidence base cannot answer; correct = decline

Ground truths for A and B are computed from the curated data files (not typed by hand),
so the benchmark stays consistent with the versioned evidence base.
Run:  python benchmark/build_benchmark.py
"""
from __future__ import annotations

import json
from pathlib import Path

from wwc27_medagent import core

OUT = Path(__file__).with_name("questions.jsonl")
ev = {e["id"]: e for e in core.evidence()}
V = core.venues()


def num(qid, q, value, unit, tol, route, refs):
    return {"id": qid, "set": q[0], "question": q[1], "answer_type": "number", "ground_truth": value,
            "unit": unit, "tolerance": tol, "expected_route": route, "refs": refs}


def cat(qid, q, items, route, refs, exact=True):
    return {"id": qid, "set": q[0], "question": q[1], "answer_type": "set", "ground_truth": sorted(items),
            "exact_match": exact, "expected_route": route, "refs": refs}


def items() -> list[dict]:
    A = "reproduction"
    rows = [
        num("A01", (A, "What is the mean daily maximum temperature in Fortaleza in July?"), V["fortaleza"]["july"]["tmax"], "°C", 0.05, ["get_venue_profile"], ["INMET"]),
        num("A02", (A, "What is the mean relative humidity in Brasília in July?"), V["brasilia"]["july"]["rh"], "%", 0.5, ["get_venue_profile"], ["INMET"]),
        num("A03", (A, "What is the daily mean temperature in Porto Alegre in July?"), V["porto_alegre"]["july"]["tmean"], "°C", 0.05, ["get_venue_profile"], ["INMET"]),
        num("A04", (A, "How much rain falls in Recife in June on average?"), V["recife"]["june"]["precip_mm"], "mm", 0.5, ["get_venue_profile"], ["INMET"]),
        num("A05", (A, "At what elevation is Brasília?"), V["brasilia"]["elevation_m"], "m", 1, ["get_venue_profile"], ["INMET"]),
        num("A06", (A, "At what elevation is Belo Horizonte?"), V["belo_horizonte"]["elevation_m"], "m", 1, ["get_venue_profile"], ["INMET"]),
        num("A07", (A, "On what day of July 2027 is the Women's World Cup final played?"), 25, "day of July", 0, ["tournament_facts"], ["FIFA2027"]),
        num("A08", (A, "On what day of July 2027 does the group stage end?"), 8, "day of July", 0, ["tournament_facts"], ["FIFA2027"]),
        num("A09", (A, "What was the overall time-loss injury incidence at the 2022 men's World Cup in Qatar (per 1000 h)?"), ev["E05"]["values"]["overall"], "/1000 h", 0.05, ["find_evidence"], ["Serner2025"]),
        num("A10", (A, "What percentage of time-loss illnesses at Qatar 2022 were respiratory infections?"), ev["E06"]["values"]["respiratory_pct"], "%", 0.5, ["find_evidence"], ["Serner2025"]),
        num("A11", (A, "What was the time-loss injury incidence at the 2023 Women's World Cup (per 1000 h)?"), ev["E10"]["values"]["overall"], "/1000 h", 0.05, ["find_evidence"], ["Lu2026"]),
        num("A12", (A, "What was the match time-loss injury incidence at the 2023 Women's World Cup (per 1000 match hours)?"), ev["E10"]["values"]["match"], "/1000 h", 0.05, ["find_evidence"], ["Lu2026"]),
        num("A13", (A, "What proportion of time-loss injuries at the 2023 Women's World Cup involved contact?"), ev["E10"]["values"]["contact_pct"], "%", 0.5, ["find_evidence"], ["Lu2026"]),
        num("A14", (A, "How many injury stoppages per 1000 match-hours occurred in women's matches at the 2019 Women's World Cup?"), ev["E13"]["values"]["women_rate"], "/1000 match-h", 0.05, ["find_evidence"], ["Donmez2025"]),
        num("A15", (A, "By how much does neuromuscular training reduce ACL injuries in female athletes (percent)?"), ev["E25"]["values"]["acl_reduction_pct"], "%", 0.5, ["find_evidence"], ["Bullock2025"]),
        num("A16", (A, "What percentage of elite English female footballers screened had a major cardiac condition?"), ev["E26"]["values"]["major_pct"], "%", 0.05, ["find_evidence"], ["Yamagata2026"]),
        num("A17", (A, "What is the median number of days lost after an ACL injury in UEFA women's elite club football?"), ev["E24"]["values"]["acl_median_days"], "days", 0.5, ["find_evidence"], ["Hallen2024"]),
        num("A18", (A, "How many match injuries per match were reported at the 2014 World Cup in Brazil?"), ev["E01"]["values"]["per_match"], "per match", 0.005, ["find_evidence"], ["Junge2015"]),
        num("A19", (A, "In which minute of each half were hydration breaks taken at the 2026 men's World Cup?"), ev["E09"]["values"]["minute"], "min", 0, ["find_evidence"], ["FIFA2025"]),
        num("A20", (A, "What percentage of medical staff at the 2023 Women's World Cup felt pressured by coaching staff when assessing suspected concussion?"), ev["E18"]["values"]["pressure_coaches_pct"], "%", 0.5, ["find_evidence"], ["Wilke2024"]),
        num("A21", (A, "What is the WHO 2021 guideline level for 24-hour PM2.5?"), ev["E37"]["values"]["pm25_24h"], "ug/m3", 0.05, ["get_air_quality", "find_evidence"], ["WHO_AQG2021"]),
        num("A22", (A, "What is the WHO 2021 guideline level for annual PM2.5?"), ev["E37"]["values"]["pm25_annual"], "ug/m3", 0.05, ["get_air_quality", "find_evidence"], ["WHO_AQG2021"]),
        num("A23", (A, "Under the 2026 anti-doping rules, what is the maximum permitted inhaled salbutamol dose over 24 hours?"), ev["E38"]["values"]["salbutamol_ug"], "ug", 0.5, ["plan_respiratory_care", "find_evidence"], ["WADA2026"]),
        num("A24", (A, "Under the 2026 anti-doping rules, what is the maximum permitted inhaled formoterol dose over 24 hours?"), ev["E38"]["values"]["formoterol_ug"], "ug", 0.5, ["plan_respiratory_care", "find_evidence"], ["WADA2026"]),
        num("A25", (A, "What is the upper end of the reported range of respiratory conditions among elite athletes (percent)?"), ev["E34"]["values"]["prevalence_high_pct"], "%", 0.5, ["find_evidence"], ["Ora2024"]),
    ]

    B = "application"
    itin = core.travel_burden(["Sao Paulo", "Fortaleza", "Recife", "Porto Alegre"])
    h1 = core.heat_risk(30, 50)
    h2 = core.heat_risk(28, 85)
    fort = core.venue_profile("Fortaleza")["months"]["june"]
    yf_q = ["Salvador", "Brasilia", "Porto Alegre"]
    yf = [c for c in yf_q if core.venue_profile(c)["yellow_fever_vaccine_cdc_2026"].startswith("recommended")]
    cl = core.screening_checklist("in_tournament", ["heat_environment"], ["Rio de Janeiro", "Recife", "Belo Horizonte"])
    july_mean = {V[k]["city"]: core.venue_profile(k)["months"]["july"]["indicative_swbgt_mean_c"] for k in V}
    coolest = min(july_mean, key=july_mean.get)
    rows += [
        num("B01", (B, "What is the great-circle distance between Porto Alegre and Fortaleza?"), core.distance_km("Porto Alegre", "Fortaleza"), "km", 0.02, ["calculate_travel_burden"], []),
        num("B02", (B, "Our base camp is São Paulo and we play in Fortaleza, then Recife, then Porto Alegre. What total distance do we fly (great-circle)?"), itin["total_km"], "km", 0.02, ["calculate_travel_burden"], []),
        num("B03", (B, "The forecast is 30 °C and 50% relative humidity. What is the indicative simplified WBGT?"), h1["indicative_swbgt_c"], "°C", 0.2, ["estimate_heat_risk"], ["FIFPRO"]),
        cat("B04", (B, "A match forecast is 28 °C with 85% humidity. Which heat band does this fall into (low, moderate, high or very high)?"), [h2["band"]], ["estimate_heat_risk"], ["FIFPRO"]),
        num("B05", (B, "What is the indicative simplified WBGT at the mean daily maximum temperature in Fortaleza in June?"), fort["indicative_swbgt_max_c"], "°C", 0.2, ["get_venue_profile"], ["INMET"]),
        cat("B06", (B, "Among Salvador, Brasília and Porto Alegre, for which host cities does CDC recommend yellow fever vaccination for the whole state?"), yf, ["get_venue_profile"], ["CDC2026"]),
        cat("B07", (B, "We play in Rio de Janeiro, Recife and Belo Horizonte. Which of these venues should be treated as heat-exposed (indicative sWBGT at daily maximum of 28 °C or more)?"), cl["venue_specific"]["heat_exposed_venues"], ["build_screening_checklist", "get_venue_profile"], ["INMET"]),
        cat("B08", (B, "Is yellow fever vaccination recommended for travel to Recife? Answer 'recommended' or 'not recommended'."), ["not recommended"], ["get_venue_profile"], ["CDC2026"]),
        cat("B09", (B, "Which host city has the lowest indicative daily-mean sWBGT in July?"), [coolest], ["get_venue_profile"], ["INMET"]),
        cat("B11", (B, "A 24-hour PM2.5 concentration of 30 ug/m3 is forecast for a training day. Which planning band does that fall into (good, moderate, elevated, high or very high)?"), [core.pm25_band(30)["band"]], ["plan_respiratory_care", "get_air_quality"], ["WHO_AQG2021"]),
        cat("B12", (B, "Which host city's air quality is monitored by CETESB?"), ["Sao Paulo"], ["get_air_quality"], []),
        cat("B13", (B, "Among Brasília, Porto Alegre and Fortaleza, in which host city is very dry winter air the main airway concern?"), ["Brasilia"], ["get_air_quality", "get_venue_profile"], []),
        num("B10", (B, "How far is it from Rio de Janeiro to São Paulo (great-circle)?"), core.distance_km("Rio de Janeiro", "Sao Paulo"), "km", 0.02, ["calculate_travel_burden"], []),
    ]

    C = "open_ended"
    rubric = [
        ("C01", "Our base camp is São Paulo and our group matches are in Fortaleza, Recife and Porto Alegre. Draft the key elements of our pre-tournament medical plan.",
         ["heat acclimation/cooling plan for Fortaleza and Recife", "cold/wet-weather plan for Porto Alegre", "total travel ~5900 km or leg distances given",
          "yellow fever vaccination recommended for Porto Alegre (Rio Grande do Sul) and not Ceará/Pernambuco", "respiratory infection prevention", "states sWBGT is indicative / on-site WBGT needed", "provides source links"],
         ["INMET", "CDC2026", "Racinais2015", "Serner2025"]),
        ("C02", "Several of our players will be in the luteal phase for a hot, humid match. What should we consider?",
         ["higher core temperature in luteal phase", "earlier or additional cooling", "ice slurry or ice vest as best-supported cooling in females", "evidence in women is limited",
          "on-site WBGT monitoring / policy thresholds", "provides source links"], ["Giersch2020", "Convit2024", "FIFPRO"]),
        ("C03", "A player has low ferritin six weeks before the tournament. How should we handle this?",
         ["screen energy availability/REDs", "plan supplementation before the tournament", "time blood sampling away from exercise (hepcidin peaks 3-6 h)", "clinical referral/review", "provides source links"],
         ["Mountjoy2023", "Fensham2023", "SmithRyan2026"]),
        ("C04", "What cardiovascular screening should our squad have before Brazil 2027?",
         ["questionnaire and examination", "12-lead ECG with sex-appropriate interpretation", "echocardiography where indicated", "low prevalence of major conditions (~0.2%) in female players",
          "emergency action plan / AED", "provides source links"], ["Yamagata2026"]),
        ("C05", "How can we protect our concussion assessments from pressure during matches?",
         ["reports pressure from players (55%) and/or coaches (47%)", "baseline assessment", "clear medical authority / removal from play", "education of players and coaches", "provides source links"],
         ["Wilke2024"]),
        ("C06", "Design a daily in-tournament monitoring routine for our squad.",
         ["wellness/sleep measures", "illness symptom check", "menstrual cycle tracking only with consent", "playing minutes/load", "consensus surveillance definitions (football extension / female health supplement)",
          "keeps the set of measures small and consistent", "provides source links"], ["Walden2023", "Moore2023", "Tabben2025"]),
        ("C07", "What infection risks should we plan for in Brazil and how?",
         ["dengue (and/or other arboviruses such as Oropouche)", "mosquito-bite prevention", "state-dependent yellow fever vaccination", "respiratory infection as the most common tournament illness",
          "food/water hygiene", "monitor outbreak bulletins", "provides source links"], ["GurgelGoncalves2024", "Scachetti2025", "CDC2026", "Serner2025", "Lu2026"]),
        ("C08", "How should we manage ACL injury risk in the months before the tournament?",
         ["neuromuscular training ≥10 min twice weekly", "~61% ACL injury reduction", "high burden of ACL injury (~292 days)", "pre-tournament risk profiling / club-country data sharing", "provides source links"],
         ["Bullock2025", "Hallen2024", "Crossley2025"]),
        ("C09", "Should we give players NSAIDs routinely before matches?",
         ["advises against routine pre-match NSAIDs", "medication use has been high at World Cups (higher mean intake at the Women's World Cup)", "log/reconcile medication", "provides source links"],
         ["Tscholl2015"]),
        ("C11", "Two of our players have exercise-induced bronchoconstriction and we train in São Paulo in July. How should we manage them?",
         ["objective diagnosis/documented treatment plan", "inhaled corticosteroid-based treatment rather than reliever alone", "extended warm-up",
          "avoid peak-traffic hours or move hard sessions indoors when pollution is elevated", "check local air quality or monitoring agency data (CETESB)",
          "keep inhaled doses within anti-doping limits and consider a therapeutic use exemption", "provides source links"],
         ["Ora2024", "He2022", "VanMeerbeke2024", "WADA2026", "WHO_AQG2021"]),
        ("C10", "What have previous World Cups shown about illness during the tournament?",
         ["respiratory infection most common illness", "Qatar 2022: 80% (12/15) of time-loss illnesses respiratory", "Women's World Cup 2023: respiratory most frequent", "illness rates were low", "provides source links"],
         ["Serner2025", "Lu2026"]),
    ]
    for qid, q, elems, refs in rubric:
        rows.append({"id": qid, "set": C, "question": q, "answer_type": "rubric", "rubric": elems, "expected_route": ["any"], "refs": refs})

    D = "out_of_scope"
    oos = [
        ("D01", "Which team will win the 2027 Women's World Cup?"),
        ("D02", "What transfer fee did the most expensive women's player command in 2026?"),
        ("D03", "How much do tickets for the final at the Maracanã cost?"),
        ("D04", "Give me a recipe for feijoada for the team dinner."),
        ("D05", "What was the time-loss injury incidence at the 2015 Women's World Cup in Canada?"),
        ("D06", "What is the kick-off time of the opening match on 24 June 2027?"),
        ("D07", "Which hotel should our team book in Fortaleza?"),
        ("D08", "What will the WBGT be in Recife on 30 June 2027?"),
        ("D09", "What was the injury incidence at the UEFA Women's Euro 2025?"),
        ("D10", "What is the current stock price of a major kit manufacturer?"),
        ("D11", "What was the PM2.5 concentration at the 2014 World Cup final in Rio de Janeiro?"),
        ("D12", "How many players at the 2023 Women's World Cup had asthma?"),
    ]
    for qid, q in oos:
        rows.append({"id": qid, "set": D, "question": q, "answer_type": "refusal", "ground_truth": "decline",
                     "expected_route": ["find_evidence or none"], "refs": []})
    return rows


if __name__ == "__main__":
    rows = items()
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"wrote {len(rows)} items -> {OUT}", dict(Counter(r["set"] for r in rows)))
