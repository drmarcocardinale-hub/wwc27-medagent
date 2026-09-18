"""Pull air-quality data for the eight host cities, on demand or on a schedule.

Modes
  snapshot     one reading per venue per source, appended to data/airq_archive/YYYY-MM.jsonl
               and mirrored to data/airq_archive/latest.json  (default; run daily)
  climatology  June-July hourly history for the last N years -> wwc27_medagent/data/air_quality.json
               ("climatology" block, used by get_air_quality)  (run once, then yearly)
  probe        list the monitoring stations each source can see near each venue, and exit

Sources: openmeteo (no key), openaq (OPENAQ_API_KEY), waqi (WAQI_TOKEN), iqair (IQAIR_API_KEY).
Several host cities publish only through their own agency portal; `--list-sources` shows those
too, and `probe` names the best source for each venue.
Missing keys and network failures are recorded in the output, not raised.

Examples
  python scripts/pull_air_quality.py                                  # daily snapshot, all sources
  python scripts/pull_air_quality.py --sources openmeteo              # no keys needed
  python scripts/pull_air_quality.py --mode probe
  python scripts/pull_air_quality.py --mode climatology --years 3
  python scripts/pull_air_quality.py --list-sources                    # everything, incl. manual
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
            if sources.may_redistribute(rec["source"]) or args.archive_all:
                rows.append(rec)
            else:
                rec["_not_archived"] = "licence restricts redistribution"
            status = rec.get("status") or rec.get("planning_band") or rec.get("planning_band_est") or "ok"
            shown = f"{pm}" if rec.get("units") != "aqi" else f"AQI {pm} (~{est} ug/m3)"
            detail = rec.get("detail")
            km = detail.get("station_km") if isinstance(detail, dict) else None
            note = f"  station {km} km" if km is not None else ""
            flag = "" if sources.may_redistribute(rec["source"]) else "  [not archived: licence]"
            print(f"{v['city']:<15} {rec['source']:<10} pm2.5={shown:<24} {status}{note}{flag}")
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
                fresh = [l for l in idx["locations"]
                         if (sources._age_hours(l.get("last")) or 1e9) <= 24]
                pm25 = [l for l in fresh if any(s["parameter"] in ("pm25", "pm2_5")
                                                for s in l["sensors"])]
                print(f"  openaq: {len(idx['locations'])} station(s), {len(fresh)} reporting in the "
                      f"last 24 h, {len(pm25)} of those measuring PM2.5")
                for loc in idx["locations"][:5]:
                    age = sources._age_hours(loc.get("last"))
                    when = "never" if age is None else (
                        f"{age:.0f}h ago" if age < 72 else f"STALE {age/24:.0f}d")
                    print(f"    - {loc['name']} ({loc['provider']}, {loc['grade']}) "
                          f"{','.join(s['parameter'] for s in loc['sensors'] if s['parameter'])} "
                          f"{loc['distance_km']}km {when}")
        if "waqi" in args.sources:
            w = sources.waqi_nearest(key, v["lat"], v["lon"], timeout=args.timeout)
            d = w.get("detail") or {}
            if isinstance(d, dict) and d.get("station"):
                km, verdict = d.get("station_km"), w.get("status") or "usable"
                print(f"  waqi: {d['station']} — {km} km — {verdict}")
            else:
                print(f"  waqi: {d or w.get('status')}")
        if "iqair" in args.sources:
            q = sources.iqair_nearest_city(key, v["lat"], v["lon"], timeout=args.timeout)
            qd = q.get("detail") or {}
            if isinstance(qd, dict) and qd.get("city"):
                print(f"  iqair: {qd['city']} - {qd.get('station_km')} km - "
                      f"PM2.5 {(q.get('values') or {}).get('pm2_5')} ug/m3 - "
                      f"{q.get('status') or 'usable'}")
            else:
                print(f"  iqair: {qd or q.get('status')}")
        if "openmeteo" in args.sources:
            m = sources.open_meteo_current(key, v["lat"], v["lon"], timeout=args.timeout)
            print(f"  openmeteo: {'ok' if m.get('status') != 'error' else m['detail']}")
        print("  best source for this venue: "
              + " > ".join(b["name"] for b in sources.best_sources(key)))
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
    ap.add_argument("--sources", default=",".join(sources.DEFAULT_SOURCES),
                    help="comma list: openmeteo, openaq, waqi, iqair")
    ap.add_argument("--list-sources", action="store_true",
                    help="print every known source (automated and manual) and exit")
    ap.add_argument("--venues", default="", help="comma list of venue keys or city names (default: all)")
    ap.add_argument("--years", type=int, default=3, help="climatology mode: past years to pool")
    ap.add_argument("--radius", type=int, default=50000, help="probe mode: station search radius (m)")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--archive-all", action="store_true",
                    help="also archive sources whose licence restricts redistribution "
                         "(Google, IQAir). Do not use in a public repository.")
    a = ap.parse_args()
    if getattr(a, 'list_sources', False):
        for sid, meta in sources.registry().items():
            tag = 'auto ' if meta['automated'] else 'MANUAL'
            key = f" key={meta['key']}" if meta.get('key') else ''
            print(f"{tag}  {sid:<16} {meta['name']:<38} {meta['kind']:<20} "
                  f"{meta['cadence']:<22}{key}")
            print(f"        covers: {meta['covers']}")
            if meta.get('how'):
                print(f"        how:    {meta['how']}")
            print(f"        {meta['url']}")
        return 0
    a.sources = [s.strip() for s in a.sources.split(",") if s.strip()]
    a.venues = [v.strip() for v in a.venues.split(",") if v.strip()] or None
    return {"snapshot": do_snapshot, "climatology": do_climatology, "probe": do_probe}[a.mode](a)


if __name__ == "__main__":
    raise SystemExit(main())
