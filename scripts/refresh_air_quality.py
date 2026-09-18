"""Fill the June–July air-quality climatology for the eight host cities.

Run this on a machine with internet access:

    python scripts/refresh_air_quality.py               # last 3 years, 1 June – 31 July
    python scripts/refresh_air_quality.py --years 5

It queries the Open-Meteo air-quality archive (CAMS global reanalysis/forecast) at each venue's
coordinates, computes June–July means and 95th percentiles for PM2.5, PM10, NO2 and ozone, and
writes them into wwc27_medagent/data/air_quality.json under "climatology", with provenance.
Values represent a model grid cell, not the stadium: treat them as context, not measurements.
Re-run it as part of a living-mode update and commit the change with the changelog entry.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from wwc27_medagent import core

ARCHIVE = "https://air-quality-api.open-meteo.com/v1/air-quality"
DATA = Path(core.__file__).with_name("data") / "air_quality.json"
VARS = {"pm2_5": "pm2_5", "pm10": "pm10", "no2": "nitrogen_dioxide", "o3": "ozone"}


def fetch_city(lat: float, lon: float, year: int, timeout: float) -> dict[str, list[float]]:
    url = (f"{ARCHIVE}?latitude={lat:.3f}&longitude={lon:.3f}"
           f"&hourly={','.join(VARS.values())}"
           f"&start_date={year}-06-01&end_date={year}-07-31&timezone=America%2FSao_Paulo")
    with urllib.request.urlopen(url, timeout=timeout) as fh:
        data = json.load(fh)
    hourly = data.get("hourly", {})
    return {k: [v for v in hourly.get(api, []) if v is not None] for k, api in VARS.items()}


def summarise(series: list[float]) -> dict | None:
    if len(series) < 24:
        return None
    s = sorted(series)
    return {"mean": round(st.mean(series), 1),
            "p95": round(s[int(0.95 * (len(s) - 1))], 1),
            "hours": len(series)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=3, help="how many past years of June-July to average")
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()

    years = [date.today().year - i for i in range(1, a.years + 1)]
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for key, v in core.venues().items():
        pooled: dict[str, list[float]] = {k: [] for k in VARS}
        got: list[int] = []
        for y in years:
            try:
                series = fetch_city(v["lat"], v["lon"], y, a.timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                print(f"  {v['city']} {y}: skipped ({e})")
                continue
            if any(series.values()):
                got.append(y)
                for k in VARS:
                    pooled[k].extend(series[k])
        stats = {k: summarise(vals) for k, vals in pooled.items()}
        if not got or not any(stats.values()):
            print(f"{v['city']}: no data")
            continue
        out[key] = {"years": got, "period": "1 June - 31 July", "units": "ug/m3", **stats}
        print(f"{v['city']}: PM2.5 mean {stats['pm2_5']['mean'] if stats['pm2_5'] else 'NA'} ug/m3 "
              f"over {got}")

    if not out:
        print("Nothing written: no data could be retrieved (check internet access).")
        return 1
    payload["climatology"] = out
    payload["_meta"]["climatology_status"] = (
        f"Populated {datetime.now(timezone.utc).date().isoformat()} from the Open-Meteo air-quality "
        f"archive (CAMS) for June-July {min(min(v['years']) for v in out.values())}-"
        f"{max(max(v['years']) for v in out.values())}. Model grid-cell values, not station measurements.")
    DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote climatology for {len(out)} cities to {DATA}")
    print("Now run: pytest -q  and add a CHANGELOG entry before releasing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
