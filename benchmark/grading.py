"""Automatic grading for benchmark sets A (reproduction), B (application) and D (out-of-scope).
Set C (open-ended) is scored by two human raters (see rater_sheet.py)."""
from __future__ import annotations

import json
import re
import unicodedata

REFUSAL_PAT = re.compile(
    r"(i don'?t know|do not know|not (?:in|within|covered by) (?:the|my|this) (?:evidence|scope|sources)|"
    r"outside (?:the|my) (?:evidence|scope)|cannot (?:answer|determine|provide)|can'?t (?:answer|determine|provide)|"
    r"no (?:curated )?source|not available in|unable to (?:answer|provide)|out of scope)", re.I)


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def parse_response(text: str) -> dict:
    """Agents are asked to end with a JSON object {answer, value, items, refused, sources}.
    Falls back to free text if the JSON block is missing."""
    m = re.findall(r"\{[\s\S]*\}", text or "")
    for block in reversed(m):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict) and "answer" in obj:
                return obj
        except json.JSONDecodeError:
            continue
    return {"answer": text or "", "value": None, "items": [], "refused": bool(REFUSAL_PAT.search(text or "")), "sources": []}


def _first_number(text: str):
    m = re.search(r"-?\d+(?:[.,]\d+)?", (text or "").replace(",", ""))
    return float(m.group()) if m else None


def grade(item: dict, response: dict) -> dict:
    t = item["answer_type"]
    refused = bool(response.get("refused")) or bool(REFUSAL_PAT.search(str(response.get("answer", ""))))
    if t == "refusal":
        return {"correct": refused, "detail": "declined" if refused else "answered out-of-scope question"}
    if refused:
        return {"correct": False, "detail": "declined an in-scope question"}
    if t == "number":
        v = response.get("value")
        if v is None:
            v = _first_number(str(response.get("answer", "")))
        try:
            v = float(v)
        except (TypeError, ValueError):
            return {"correct": False, "detail": "no numeric value"}
        gt, tol = float(item["ground_truth"]), float(item["tolerance"])
        ok = abs(v - gt) <= (tol * abs(gt) if 0 < tol < 0.1 and item["unit"] == "km" else tol)
        return {"correct": ok, "detail": f"value={v} gt={gt} tol={tol}"}
    if t == "set":
        got = response.get("items") or []
        if not got and response.get("answer"):
            got = [response["answer"]]
        got_n = {_ascii(str(x)) for x in got}
        gt_n = {_ascii(x) for x in item["ground_truth"]}
        if item.get("exact_match", True):
            ok = got_n == gt_n
        else:
            ok = gt_n <= got_n
        return {"correct": ok, "detail": f"items={sorted(got_n)} gt={sorted(gt_n)}"}
    return {"correct": None, "detail": "human-rated (rubric)"}
