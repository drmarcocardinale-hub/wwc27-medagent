"""Air-quality data sources that can be pulled on a schedule.

Three sources are supported, all reachable from an ordinary machine:

  openmeteo  Open-Meteo air-quality API (CAMS global/European forecast and archive).
             No key. Model grid values (~11 km in Europe, ~40 km globally), hourly,
             forecast and history from 2013. Attribution to CAMS and Open-Meteo required.
  openaq     OpenAQ v3. Aggregates reference monitoring networks worldwide. Free API key
             (header X-API-Key) from explore.openaq.org/register. Station measurements,
             so coverage depends on what each country publishes - use `probe` first.
  waqi       World Air Quality Index (aqicn.org). Free token. Real-time station feeds,
             including CETESB's network in Sao Paulo. Values are AQI, not ug/m3, except
             where the feed reports concentrations; free use is non-commercial and
             requires attribution to WAQI and the originating agency.

Every fetcher returns the same record shape so the puller can store them side by side:

    {"source": ..., "venue": ..., "retrieved_at": ..., "observed_at": ...,
     "kind": "model_forecast" | "station" | "model_archive",
     "units": "ug/m3" | "aqi", "values": {"pm2_5": .., "pm10": .., "no2": .., "o3": ..},
     "detail": {...}, "attribution": "..."}

Failures never raise: they come back as {"source": ..., "status": "error", "detail": ...},
so a scheduled run records the gap instead of dying.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "WWC27-MedAgent/0.3 (+https://github.com/OWNER/wwc27-medagent)"
OPEN_METEO = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPENAQ = "https://api.openaq.org/v3"
WAQI = "https://api.waqi.info"

ATTRIBUTION = {
    "openmeteo": "Air-quality data from Open-Meteo (open-meteo.com), based on CAMS (Copernicus Atmosphere Monitoring Service) ENSEMBLE data.",
    "openaq": "Station data via OpenAQ (openaq.org); original measurements belong to the reporting agencies.",
    "waqi": "Real-time data via the World Air Quality Index project (aqicn.org) and the originating monitoring agency; non-commercial use with attribution.",
}
POLLUTANTS = ("pm2_5", "pm10", "no2", "o3")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(url: str, headers: dict[str, str] | None = None, timeout: float = 30.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.load(fh)


def _error(source: str, venue: str, exc: Exception | str) -> dict:
    return {"source": source, "venue": venue, "retrieved_at": _now(), "status": "error",
            "detail": str(exc)}


# --------------------------------------------------------------------------- Open-Meteo
def open_meteo_current(venue: str, lat: float, lon: float, timeout: float = 30.0) -> dict:
    """Current (nowcast) concentrations for a venue's coordinates."""
    q = urllib.parse.urlencode({
        "latitude": f"{lat:.3f}", "longitude": f"{lon:.3f}",
        "current": "pm2_5,pm10,nitrogen_dioxide,ozone,carbon_monoxide,dust",
        "timezone": "America/Sao_Paulo"})
    try:
        data = _get(f"{OPEN_METEO}?{q}", timeout=timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return _error("openmeteo", venue, e)
    cur = data.get("current", {})
    return {"source": "openmeteo", "venue": venue, "retrieved_at": _now(),
            "observed_at": cur.get("time"), "kind": "model_forecast", "units": "ug/m3",
            "values": {"pm2_5": cur.get("pm2_5"), "pm10": cur.get("pm10"),
                       "no2": cur.get("nitrogen_dioxide"), "o3": cur.get("ozone")},
            "detail": {"co": cur.get("carbon_monoxide"), "dust": cur.get("dust"),
                       "model": "CAMS via Open-Meteo"},
            "attribution": ATTRIBUTION["openmeteo"]}


def open_meteo_range(venue: str, lat: float, lon: float, start: str, end: str,
                     timeout: float = 60.0) -> dict:
    """Hourly series between two ISO dates (archive or forecast window)."""
    q = urllib.parse.urlencode({
        "latitude": f"{lat:.3f}", "longitude": f"{lon:.3f}",
        "hourly": "pm2_5,pm10,nitrogen_dioxide,ozone",
        "start_date": start, "end_date": end, "timezone": "America/Sao_Paulo"})
    try:
        data = _get(f"{OPEN_METEO}?{q}", timeout=timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return _error("openmeteo", venue, e)
    h = data.get("hourly", {})
    series = {"pm2_5": h.get("pm2_5", []), "pm10": h.get("pm10", []),
              "no2": h.get("nitrogen_dioxide", []), "o3": h.get("ozone", [])}
    return {"source": "openmeteo", "venue": venue, "retrieved_at": _now(),
            "observed_at": f"{start}/{end}", "kind": "model_archive", "units": "ug/m3",
            "time": h.get("time", []), "series": series,
            "attribution": ATTRIBUTION["openmeteo"]}


# --------------------------------------------------------------------------- OpenAQ v3
def openaq_locations(venue: str, lat: float, lon: float, radius_m: int = 25000,
                     api_key: str | None = None, limit: int = 20, timeout: float = 30.0) -> dict:
    """Monitoring stations within `radius_m` of the venue (max 25 km in the v3 API)."""
    key = api_key or os.environ.get("OPENAQ_API_KEY")
    if not key:
        return _error("openaq", venue, "no OPENAQ_API_KEY set (free key: explore.openaq.org/register)")
    q = urllib.parse.urlencode({"coordinates": f"{lat:.4f},{lon:.4f}",
                                "radius": min(radius_m, 25000), "limit": limit})
    try:
        data = _get(f"{OPENAQ}/locations?{q}", headers={"X-API-Key": key}, timeout=timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return _error("openaq", venue, e)
    locs = [{"id": r.get("id"), "name": r.get("name"),
             "provider": (r.get("provider") or {}).get("name"),
             "sensors": [s.get("parameter", {}).get("name") for s in r.get("sensors", [])],
             "last": (r.get("datetimeLast") or {}).get("utc")} for r in data.get("results", [])]
    return {"source": "openaq", "venue": venue, "retrieved_at": _now(), "kind": "station_index",
            "locations": locs, "attribution": ATTRIBUTION["openaq"]}


def openaq_latest(venue: str, lat: float, lon: float, radius_m: int = 25000,
                  api_key: str | None = None, timeout: float = 30.0) -> dict:
    """Latest station values near the venue, averaged across stations per pollutant."""
    key = api_key or os.environ.get("OPENAQ_API_KEY")
    idx = openaq_locations(venue, lat, lon, radius_m, key, timeout=timeout)
    if idx.get("status") == "error":
        return idx
    if not idx["locations"]:
        return {"source": "openaq", "venue": venue, "retrieved_at": _now(), "kind": "station",
                "status": "no_stations", "units": "ug/m3", "values": {},
                "detail": {"radius_m": radius_m},
                "attribution": ATTRIBUTION["openaq"]}
    buckets: dict[str, list[float]] = {p: [] for p in POLLUTANTS}
    seen, latest_time = [], None
    for loc in idx["locations"]:
        try:
            data = _get(f"{OPENAQ}/locations/{loc['id']}/latest", headers={"X-API-Key": key},
                        timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
        seen.append(loc["name"])
        for r in data.get("results", []):
            name = str(((r.get("parameter") or {}).get("name") or r.get("parameter") or "")).lower()
            name = {"pm25": "pm2_5", "pm2.5": "pm2_5"}.get(name, name)
            val = r.get("value")
            t = (r.get("datetime") or {}).get("utc") if isinstance(r.get("datetime"), dict) else r.get("datetime")
            if name in buckets and isinstance(val, (int, float)):
                buckets[name].append(float(val))
                latest_time = max(filter(None, [latest_time, t])) if (latest_time or t) else None
    values = {p: round(sum(v) / len(v), 1) for p, v in buckets.items() if v}
    return {"source": "openaq", "venue": venue, "retrieved_at": _now(),
            "observed_at": latest_time, "kind": "station", "units": "ug/m3", "values": values,
            "detail": {"stations": seen, "n_stations": len(seen), "radius_m": radius_m,
                       "note": "mean across stations within the radius; station siting varies"},
            "attribution": ATTRIBUTION["openaq"]}


# --------------------------------------------------------------------------- WAQI
def waqi_nearest(venue: str, lat: float, lon: float, token: str | None = None,
                 timeout: float = 30.0) -> dict:
    """Nearest WAQI station feed. Note: iaqi values are AQI sub-indices, not ug/m3."""
    tok = token or os.environ.get("WAQI_TOKEN")
    if not tok:
        return _error("waqi", venue, "no WAQI_TOKEN set (free token: aqicn.org/data-platform/token/)")
    url = f"{WAQI}/feed/geo:{lat:.4f};{lon:.4f}/?token={urllib.parse.quote(tok)}"
    try:
        data = _get(url, timeout=timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return _error("waqi", venue, e)
    if data.get("status") != "ok":
        return _error("waqi", venue, f"api status {data.get('status')}: {data.get('data')}")
    d = data.get("data", {})
    iaqi = {k: (v or {}).get("v") for k, v in (d.get("iaqi") or {}).items()}
    return {"source": "waqi", "venue": venue, "retrieved_at": _now(),
            "observed_at": (d.get("time") or {}).get("iso"), "kind": "station", "units": "aqi",
            "values": {"pm2_5": iaqi.get("pm25"), "pm10": iaqi.get("pm10"),
                       "no2": iaqi.get("no2"), "o3": iaqi.get("o3")},
            "detail": {"aqi": d.get("aqi"), "station": (d.get("city") or {}).get("name"),
                       "attributions": [a.get("name") for a in d.get("attributions", [])],
                       "note": "AQI sub-indices (US EPA scale), not concentrations; convert before "
                               "comparing with WHO guideline levels"},
            "attribution": ATTRIBUTION["waqi"]}


FETCHERS = {"openmeteo": open_meteo_current, "openaq": openaq_latest, "waqi": waqi_nearest}


def snapshot(venue: str, lat: float, lon: float, sources: list[str], **kw) -> list[dict]:
    out = []
    for s in sources:
        fn = FETCHERS.get(s)
        out.append(fn(venue, lat, lon, **kw) if fn else _error(s, venue, "unknown source"))
    return out
