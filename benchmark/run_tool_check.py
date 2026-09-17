"""Tool-layer check (no language model): for every A/B item, call the expected tool with oracle
arguments and confirm the ground truth is reachable from the tool output; for every D item,
record whether the evidence-retrieval tool already declines. This isolates tool correctness from
agent reasoning, analogous to Paper2Agent's automated tool validation.

Run: python benchmark/run_tool_check.py  -> benchmark/results/tool_check.json
"""
from __future__ import annotations

import json
from pathlib import Path

from wwc27_medagent import core

HERE = Path(__file__).parent
ITEMS = [json.loads(l) for l in (HERE / "questions.jsonl").open(encoding="utf-8")]

# Oracle routes: (tool call, extractor) per item id.
ORACLE = {
    "A01": lambda: core.venue_profile("Fortaleza")["months"]["july"]["tmax"],
    "A02": lambda: core.venue_profile("Brasilia")["months"]["july"]["rh"],
    "A03": lambda: core.venue_profile("Porto Alegre")["months"]["july"]["tmean"],
    "A04": lambda: core.venue_profile("Recife")["months"]["june"]["precip_mm"],
    "A05": lambda: core.venue_profile("Brasilia")["elevation_m"],
    "A06": lambda: core.venue_profile("Belo Horizonte")["elevation_m"],
    "A07": lambda: int(core.tournament()["final"][8:10]),
    "A08": lambda: int(core.tournament()["group_stage_end"][8:10]),
    "B01": lambda: core.distance_km("Porto Alegre", "Fortaleza"),
    "B02": lambda: core.travel_burden(["Sao Paulo", "Fortaleza", "Recife", "Porto Alegre"])["total_km"],
    "B03": lambda: core.heat_risk(30, 50)["indicative_swbgt_c"],
    "B04": lambda: [core.heat_risk(28, 85)["band"]],
    "B05": lambda: core.venue_profile("Fortaleza")["months"]["june"]["indicative_swbgt_max_c"],
    "B06": lambda: sorted(c for c in ["Salvador", "Brasilia", "Porto Alegre"]
                          if core.venue_profile(c)["yellow_fever_vaccine_cdc_2026"].startswith("recommended")),
    "B07": lambda: sorted(core.screening_checklist("in_tournament", ["heat_environment"],
                                                   ["Rio de Janeiro", "Recife", "Belo Horizonte"])["venue_specific"]["heat_exposed_venues"]),
    "B08": lambda: ["not recommended" if core.venue_profile("Recife")["yellow_fever_vaccine_cdc_2026"].startswith("not") else "recommended"],
    "B09": lambda: [min(core.venues(), key=lambda k: core.venue_profile(k)["months"]["july"]["indicative_swbgt_mean_c"])
                    .replace("porto_alegre", "Porto Alegre")],
    "B10": lambda: core.distance_km("Rio de Janeiro", "Sao Paulo"),
}


def evidence_route(item):
    """For evidence questions: does find_evidence(question) surface the expected source in its top 3?"""
    hits = core.find_evidence(item["question"])["hits"][:3]
    return any(h["source"]["key"] in item["refs"] for h in hits), [h["id"] for h in hits]


def main():
    out = {"A_B": [], "D": []}
    for it in ITEMS:
        if it["set"] in ("reproduction", "application"):
            if it["id"] in ORACLE:
                got = ORACLE[it["id"]]()
                if it["answer_type"] == "number":
                    ok = abs(float(got) - float(it["ground_truth"])) < 1e-6
                else:
                    ok = sorted(got) == sorted(it["ground_truth"])
                out["A_B"].append({"id": it["id"], "route": "oracle tool call", "ok": ok, "got": got})
            else:
                ok, ids = evidence_route(it)
                out["A_B"].append({"id": it["id"], "route": "find_evidence(question text)", "ok": ok, "top3": ids})
        elif it["set"] == "out_of_scope":
            r = core.find_evidence(it["question"])
            out["D"].append({"id": it["id"], "retrieval_declined": not r["hits"],
                             "returned": [h["id"] for h in r["hits"]]})
    hold = json.loads((HERE / "retrieval_holdout.json").read_text(encoding="utf-8"))
    out["holdout_in_scope"] = []
    for x in hold["in_scope"]:
        ids = [h["id"] for h in core.find_evidence(x["q"])["hits"][:3]]
        out["holdout_in_scope"].append({"q": x["q"], "expect": x["expect"], "top3": ids, "ok": x["expect"] in ids})
    out["holdout_out_of_scope"] = []
    for q in hold["out_of_scope"]:
        r = core.find_evidence(q)
        out["holdout_out_of_scope"].append({"q": q, "declined": not r["hits"], "returned": [h["id"] for h in r["hits"]]})
    ab_ok = sum(x["ok"] for x in out["A_B"])
    d_ok = sum(x["retrieval_declined"] for x in out["D"])
    out["summary"] = {"A_B_reachable": f"{ab_ok}/{len(out['A_B'])}",
                      "D_declined_at_retrieval": f"{d_ok}/{len(out['D'])}",
                      "holdout_in_scope_top3": f"{sum(x['ok'] for x in out['holdout_in_scope'])}/{len(out['holdout_in_scope'])}",
                      "holdout_out_of_scope_declined": f"{sum(x['declined'] for x in out['holdout_out_of_scope'])}/{len(out['holdout_out_of_scope'])}",
                      "note": "Retrieval rules were revised while developing set D, so D is a development set; the held-out lists were run once without tuning. Items not declined at retrieval return related but non-matching evidence; the agent must recognise the mismatch (tested in the end-to-end evaluation)."}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "tool_check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out["summary"], indent=1))
    for x in out["A_B"]:
        if not x["ok"]:
            print("FAIL", x)
    for x in out["D"]:
        if not x["retrieval_declined"]:
            print("D not declined at retrieval:", x)


if __name__ == "__main__":
    main()
