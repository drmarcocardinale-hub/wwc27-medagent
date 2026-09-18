"""Benchmark integrity: item counts, ground truths reproducible from the tools, grader behaviour."""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

from grading import grade, parse_response  # noqa: E402

ITEMS = [json.loads(l) for l in (ROOT / "benchmark" / "questions.jsonl").open(encoding="utf-8")]


def test_benchmark_composition():
    c = Counter(i["set"] for i in ITEMS)
    assert c == {"reproduction": 25, "application": 13, "open_ended": 11, "out_of_scope": 12}
    assert len({i["id"] for i in ITEMS}) == 61


def test_benchmark_file_is_up_to_date():
    import build_benchmark
    assert build_benchmark.items() == ITEMS, "run python benchmark/build_benchmark.py"


def test_every_scored_item_is_reachable_through_the_tools():
    out = subprocess.run([sys.executable, str(ROOT / "benchmark" / "run_tool_check.py")],
                         capture_output=True, text=True, check=True).stdout
    assert '"A_B_reachable": "38/38"' in out


def test_rubric_items_have_sources():
    refs = json.loads((ROOT / "wwc27_medagent" / "data" / "references.json").read_text(encoding="utf-8"))
    for i in ITEMS:
        for r in i["refs"]:
            assert r in refs, (i["id"], r)
        if i["set"] == "open_ended":
            assert len(i["rubric"]) >= 4


def _item(qid):
    return next(i for i in ITEMS if i["id"] == qid)


def test_grader_numeric():
    it = _item("A01")
    assert grade(it, {"answer": "30.6 °C", "value": 30.6})["correct"]
    assert not grade(it, {"answer": "31 °C", "value": 31})["correct"]
    assert grade(it, parse_response('It is about 30.6 °C.\n{"answer": "30.6", "value": 30.6, "items": [], "refused": false}'))["correct"]


def test_grader_relative_km_tolerance():
    it = _item("B01")
    assert grade(it, {"answer": "", "value": it["ground_truth"] * 1.015})["correct"]
    assert not grade(it, {"answer": "", "value": it["ground_truth"] * 1.05})["correct"]


def test_air_quality_items_present():
    ids = {i["id"] for i in ITEMS}
    assert {"A21", "A23", "B11", "B12", "C11", "D11"} <= ids
    assert grade(_item("B11"), {"answer": "", "items": ["elevated"]})["correct"]


def test_grader_sets_and_refusals():
    b06 = _item("B06")
    assert grade(b06, {"answer": "", "items": ["Brasília", "Porto Alegre"]})["correct"]
    assert not grade(b06, {"answer": "", "items": ["Brasília", "Porto Alegre", "Salvador"]})["correct"]
    d = _item("D05")
    assert grade(d, {"answer": "I don't know - not in the evidence base", "refused": True})["correct"]
    assert not grade(d, {"answer": "It was 4.1 per 1000 h", "value": 4.1, "refused": False})["correct"]
    # declining an answerable question is wrong
    assert not grade(_item("A09"), {"answer": "I don't know", "refused": True})["correct"]
