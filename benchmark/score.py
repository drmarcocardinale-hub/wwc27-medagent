"""Score an evaluation run and prepare / analyse the human rating of open-ended answers.

  python benchmark/score.py results/responses_X.jsonl                  # auto-scored sets + rater sheets
  python benchmark/score.py results/responses_X.jsonl --ratings r1.csv r2.csv   # add rubric scores + agreement

Accuracy is computed per run (proportion correct) and summarised as mean ± s.e.m. across runs,
as in Paper2Agent. Rater sheets are blinded (condition hidden behind a random code).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ITEMS = {json.loads(l)["id"]: json.loads(l) for l in (HERE / "questions.jsonl").open(encoding="utf-8")}


def mean_sem(xs):
    if not xs:
        return None, None
    m = st.mean(xs)
    return m, (st.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else 0.0)


def cohen_kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("responses")
    ap.add_argument("--ratings", nargs=2, metavar=("RATER1_CSV", "RATER2_CSV"))
    ap.add_argument("--seed", type=int, default=2027)
    a = ap.parse_args()
    path = Path(a.responses)
    recs = [json.loads(l) for l in path.open(encoding="utf-8")]

    # ---- auto-scored sets
    per_run = defaultdict(lambda: defaultdict(list))  # (cond,set) -> run -> [bool]
    lat, toks = defaultdict(list), defaultdict(list)
    for r in recs:
        lat[r["condition"]].append(r["latency_s"])
        toks[r["condition"]].append(r["usage"]["input_tokens"] + r["usage"]["output_tokens"])
        if r["auto_correct"] is not None:
            per_run[(r["condition"], r["set"])][r["run"]].append(bool(r["auto_correct"]))
    table = []
    for (cond, s), runs in sorted(per_run.items()):
        accs = [100 * sum(v) / len(v) for v in runs.values()]
        m, se = mean_sem(accs)
        table.append({"condition": cond, "set": s, "n_items": len(next(iter(runs.values()))),
                      "runs": len(accs), "accuracy_mean": round(m, 1), "accuracy_sem": round(se, 1)})
    summary = {"auto_scored": table,
               "median_latency_s": {c: st.median(v) for c, v in lat.items()},
               "median_tokens": {c: st.median(v) for c, v in toks.items()}}

    # ---- blinded rater sheets for open-ended answers
    oe = [r for r in recs if r["set"] == "open_ended"]
    rng = random.Random(a.seed)
    conds = sorted({r["condition"] for r in oe})
    codes = dict(zip(conds, rng.sample(["X", "Y", "Z", "W"][:len(conds)], len(conds))))
    key_path = path.with_name(path.stem + "_blinding_key.json")
    if oe and not a.ratings:
        rows = []
        for r in oe:
            rub = ITEMS[r["id"]]["rubric"]
            for k, elem in enumerate(rub, 1):
                rows.append({"response_id": f"{r['id']}-{codes[r['condition']]}-{r['run']}", "question": r["question"],
                             "answer": r["parsed"].get("answer") or r["response_text"], "element_no": k,
                             "rubric_element": elem, "present_0_1": "", "comment": ""})
        rng.shuffle(rows)
        rows.sort(key=lambda x: (x["response_id"], x["element_no"]))
        for rater in (1, 2):
            with path.with_name(path.stem + f"_rater{rater}.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        key_path.write_text(json.dumps(codes, indent=1))
        summary["rater_sheets"] = "written (two copies); keep the blinding key away from raters"

    # ---- analyse ratings
    if a.ratings:
        codes = json.loads(key_path.read_text())
        decode = {v: k for k, v in codes.items()}
        r1 = {(x["response_id"], x["element_no"]): int(x["present_0_1"]) for x in csv.DictReader(open(a.ratings[0], encoding="utf-8"))}
        r2 = {(x["response_id"], x["element_no"]): int(x["present_0_1"]) for x in csv.DictReader(open(a.ratings[1], encoding="utf-8"))}
        keys = sorted(set(r1) & set(r2))
        v1, v2 = [r1[k] for k in keys], [r2[k] for k in keys]
        summary["inter_rater"] = {"elements": len(keys),
                                  "percent_agreement": round(100 * sum(x == y for x, y in zip(v1, v2)) / len(keys), 1),
                                  "cohen_kappa": round(cohen_kappa(v1, v2), 3)}
        # rubric score per response = mean over elements of the two raters' mean
        per_resp = defaultdict(list)
        for k in keys:
            per_resp[k[0]].append((r1[k] + r2[k]) / 2)
        by = defaultdict(lambda: defaultdict(list))
        for rid, vals in per_resp.items():
            qid, code, run = rid.rsplit("-", 2)
            by[decode[code]][int(run)].append(100 * sum(vals) / len(vals))
        summary["open_ended_rubric"] = []
        for cond, runs in sorted(by.items()):
            m, se = mean_sem([st.mean(v) for v in runs.values()])
            summary["open_ended_rubric"].append({"condition": cond, "score_mean": round(m, 1), "score_sem": round(se, 1)})

    out = path.with_name(path.stem + "_summary.json")
    out.write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
