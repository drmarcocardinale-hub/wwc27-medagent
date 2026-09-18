"""Pull air-quality data for the eight host cities, on demand or on a schedule.

Modes
  snapshot     one reading per venue per source, appended to data/airq_archive/YYYY-MM.jsonl
               and mirrored to data/airq_archive/latest.json  (default; run daily)
  climatology  June-July hourly history for the last N years -> wwc27_medagent/data/air_quality.json
               ("climatology" block, used by get_air_quality)  (run once, then yearly)
  probe        list the monitoring stations each source can see near each venue, and exit

Sources: openmeteo (no key), openaq (OPENAQ_API_KEY), waqi (WAQI_TOKEN).
Missing keys and network failures are recorded in the output, not raised.

Examples
  python scripts/pull_air_quality.py                                  # daily snapshot, all sources
  python scripts/pull_air_quality.py --sources openmeteo              # no keys needed
  python scripts/pull_air_quality.py --mode probe
  python scripts/pull_air_quality.py --mode climatology --years 3
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from datetime import date, datetime, timezone
from pathlib import Path

from wwc27_medagent import core, sources

PKG = Path(core.__file__).parent
ARCHIVE = PKG / "data" / "airq_archive"
AQ_FILE = PKG / "data" / "air_quality.json"


def _venues(only: list[str] | None):
    for key, v in core.venues().items():
        if only and key not in only and v["city"] not in only:
            continue
        yield key, v


def do_snapshot(args) -> int:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    rows: list[dict] = []
    for key, v in _venues(args.venues):
        for rec in sources.snapshot(key, v["lat"], v["lon"], args.sources, timeout=args.timeout):
            rec["city"] = v["city"]
            pm = (rec.get("values") or {}).get("pm2_5")
            far = rec.get("status") == "far_station"
            if rec.get("units") == "ug/m3" and pm is not None and not far:
                rec["planning_band"] = core.pm25_band(pm)["band"]
            # AQI is not a concentration: band the converted estimate, and label it as such.
            est = (rec.get("values_ugm3_est") or {}).get("pm2_5")
            if rec.get("units") == "aqi" and est is not None and not far:
                rec["planning_band_est"] = core.pm25_band(est)["band"]
            rows.append(rec)
            status = rec.get("status") or rec.get("planning_band") or rec.get("planning_band_est") or "ok"
            shown = f"{pm}" if rec.get("units") != "aqi" else f"AQI {pm} (~{est} ug/m3)"
            detail = rec.get("detail")
            km = detail.get("station_km") if isinstance(detail, dict) else None
            note = f"  station {km} km" if km is not None else ""
            print(f"{v['city']:<15} {rec['source']:<10} pm2.5={shown:<24} {status}{note}")
    month_file = ARCHIVE / f"{stamp:%Y-%m}.jsonl"
    with month_file.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (ARCHIVE / "latest.json").write_text(
        json.dumps({"pulled_at": stamp.isoformat(timespec="seconds"), "records": rows},
                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    ok = sum(1 for r in rows if r.get("status") not in {"error"})
    print(f"\n{ok}/{len(rows)} readings stored -> {month_file.name} and latest.json")
    return 0 if ok else 1


def do_probe(args) -> int:
    for key, v in _venues(args.venues):
        print(f"\n== {v['city']}")
        if "openaq" in args.sources:
            idx = sources.openaq_locations(key, v["lat"], v["lon"], args.radius, timeout=args.timeout)
            if idx.get("status") == "error":
                print(f"  openaq: {idx['detail']}")
            else:
                print(f"  openaq: {len(idx['locations'])} station(s) within {args.radius/1000:.0f} km")
                for loc in idx["locations"][:5]:
                    print(f"    - {loc['name']} ({loc['provider']}) {','.join(s['parameter'] for s in loc['sensors'] if s['parameter'])} {loc['distance_km']}km last={loc['last']}")
        if "waqi" in args.sources:
            w = sources.waqi_nearest(key, v["lat"], v["lon"], timeout=args.timeout)
            print(f"  waqi: {w.get('detail', {}).get('station') or w.get('detail') or w.get('status')}")
        if "openmeteo" in args.sources:
            m = sources.open_meteo_current(key, v["lat"], v["lon"], timeout=args.timeout)
            print(f"  openmeteo: {'ok' if m.get('status') != 'error' else m['detail']}")
    return 0


def _summary(series: list[float]) -> dict | None:
    vals = [v for v in series if isinstance(v, (int, float))]
    if len(vals) < 24:
        return None
    s = sorted(vals)
    return {"mean": round(st.mean(vals), 1), "p95": round(s[int(0.95 * (len(s) - 1))], 1),
            "hours": len(vals)}


def do_climatology(args) -> int:
    years = [date.today().year - i for i in range(1, args.years + 1)]
    payload = json.loads(AQ_FILE.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for key, v in _venues(args.venues):
        pooled: dict[str, list[float]] = {p: [] for p in sources.POLLUTANTS}
        got: list[int] = []
        for y in years:
            rec = sources.open_meteo_range(key, v["lat"], v["lon"], f"{y}-06-01", f"{y}-07-31",
                                           timeout=max(args.timeout, 60))
            if rec.get("status") == "error":
                print(f"  {v['city']} {y}: {rec['detail']}")
                continue
            if any(rec["series"].values()):
                got.append(y)
                for p in sources.POLLUTANTS:
                    pooled[p].extend(rec["series"][p])
        stats = {p: _summary(vals) for p, vals in pooled.items()}
        if not got or not any(stats.values()):
            print(f"{v['city']}: no data")
            continue
        out[key] = {"years": sorted(got), "period": "1 June - 31 July", "units": "ug/m3",
                    "source": "Open-Meteo air-quality archive (CAMS)", **stats}
        pm = stats["pm2_5"]
        print(f"{v['city']:<15} PM2.5 mean {pm['mean'] if pm else 'NA'} ug/m3, "
              f"p95 {pm['p95'] if pm else 'NA'} ({sorted(got)})")
    if not out:
        print("Nothing written: no data retrieved (check internet access).")
        return 1
    payload["climatology"] = out
    payload["_meta"]["climatology_status"] = (
        f"Populated {date.today().isoformat()} from the Open-Meteo air-quality archive (CAMS) for "
        f"June-July {min(min(v['years']) for v in out.values())}-"
        f"{max(max(v['years']) for v in out.values())}. Model grid-cell values, not station measurements.")
    AQ_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote climatology for {len(out)} cities. Run pytest, then add a CHANGELOG entry.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["snapshot", "climatology", "probe"], default="snapshot")
    ap.add_argument("--sources", default="openmeteo,openaq,waqi",
                    help="comma list: openmeteo, openaq, waqi")
    ap.add_argument("--venues", default="", help="comma list of venue keys or city names (default: all)")
    ap.add_argument("--years", type=int, default=3, help="climatology mode: past years to pool")
    ap.add_argument("--radius", type=int, default=50000, help="probe mode: station search radius (m)")
    ap.add_argument("--timeout", type=float, default=30.0)
    a = ap.parse_args()
    a.sources = [s.strip() for s in a.sources.split(",") if s.strip()]
    a.venues = [v.strip() for v in a.venues.split(",") if v.strip()] or None
    return {"snapshot": do_snapshot, "climatology": do_climatology, "probe": do_probe}[a.mode](a)


if __name__ == "__main__":
    raise SystemExit(main())
