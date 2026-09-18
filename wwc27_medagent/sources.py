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
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "WWC27-MedAgent/0.3 (+https://github.com/drmarcocardinale-hub/wwc27-medagent)"
OPEN_METEO = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPENAQ = "https://api.openaq.org/v3"
WAQI = "https://api.waqi.info"

ATTRIBUTION = {
    "openmeteo": "Air-quality data from Open-Meteo (open-meteo.com), based on CAMS (Copernicus Atmosphere Monitoring Service) ENSEMBLE data.",
    "openaq": "Station data via OpenAQ (openaq.org); original measurements belong to the reporting agencies.",
    "waqi": "Real-time data via the World Air Quality Index project (aqicn.org) and the originating monitoring agency; non-commercial use with attribution.",
}
POLLUTANTS = ("pm2_5", "pm10", "no2", "o3")
_PARAM_ALIASES = {"pm25": "pm2_5", "pm2.5": "pm2_5", "pm2_5": "pm2_5", "pm10": "pm10",
                  "no2": "no2", "nitrogen_dioxide": "no2", "o3": "o3", "ozone": "o3"}


def _canon(parameter: str | None) -> str:
    """Normalise a source's pollutant name ('pm25', 'PM2.5', 'ozone') to our key."""
    p = str(parameter or "").strip().lower()
    return _PARAM_ALIASES.get(p, p)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _age_hours(iso: str | None) -> float | None:
    """Hours since an ISO timestamp, or None if it is missing or unparseable."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0


# Community/low-cost sensor networks. Useful for trend, but not reference-grade instruments:
# they need correction factors and should not be read against guideline levels uncritically.
LOW_COST_PROVIDERS = {"airgradient", "habitatmap", "purpleair", "sensor.community",
                      "sensorcommunity", "clarity", "iqair", "airbeam"}


def provider_grade(provider: str | None) -> str:
    p = str(provider or "").strip().lower()
    if not p:
        return "unknown"
    return "low_cost" if any(k in p for k in LOW_COST_PROVIDERS) else "reference"


def _get(url: str, headers: dict[str, str] | None = None, timeout: float = 30.0,
         retries: int = 1, backoff: float = 2.0) -> Any:
    """GET and parse JSON, retrying once on a transient failure.

    A single venue failing while the others succeed is almost always a transient upstream error
    or rate limit, and an unretried failure leaves a hole in that day's archive.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                return json.load(fh)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            if attempt >= retries:
                raise
            time.sleep(backoff * (attempt + 1))


def _error(source: str, venue: str, exc: Exception | str) -> dict:
    return {"source": source, "venue": venue, "retrieved_at": _now(), "status": "error",
            "detail": str(exc)}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km. Used to check that a station is actually near the venue."""
    from math import asin, cos, radians, sin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * 6371.0088 * asin(sqrt(a)), 1)


# US EPA PM2.5 AQI breakpoints (2024 revision): (AQI_lo, AQI_hi, C_lo, C_hi) in ug/m3.
_PM25_AQI_BREAKS = [(0, 50, 0.0, 9.0), (51, 100, 9.1, 35.4), (101, 150, 35.5, 55.4),
                    (151, 200, 55.5, 125.4), (201, 300, 125.5, 225.4), (301, 500, 225.5, 325.4)]


def pm25_from_aqi(aqi: float | None) -> float | None:
    """Invert the US EPA PM2.5 AQI to an approximate 24 h concentration in ug/m3.

    WAQI reports AQI sub-indices, not concentrations. Comparing a raw AQI number with the WHO
    guideline levels (which are in ug/m3) overstates pollution roughly three-fold in the range
    that matters for scheduling training, so the conversion is done explicitly and the result is
    labelled as an estimate.
    """
    if aqi is None or not isinstance(aqi, (int, float)) or aqi < 0:
        return None
    for lo, hi, c_lo, c_hi in _PM25_AQI_BREAKS:
        if lo <= aqi <= hi:
            return round(c_lo + (aqi - lo) * (c_hi - c_lo) / (hi - lo), 1)
    return None


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
def openaq_locations(venue: str, lat: float, lon: float, radius_m: int = 50000,
                     api_key: str | None = None, limit: int = 20, timeout: float = 30.0) -> dict:
    """Monitoring stations within `radius_m` of the venue (max 25 km in the v3 API)."""
    key = api_key or os.environ.get("OPENAQ_API_KEY")
    if not key:
        return _error("openaq", venue, "no OPENAQ_API_KEY set (free key: explore.openaq.org/register)")
    def _fetch(query: str) -> Any:
        return _get(f"{OPENAQ}/locations?{query}", headers={"X-API-Key": key}, timeout=timeout)

    q = urllib.parse.urlencode({"coordinates": f"{lat:.4f},{lon:.4f}",
                                "radius": min(radius_m, 25000), "limit": limit})
    try:
        data = _fetch(q)
        search = f"radius {min(radius_m, 25000) / 1000:.0f} km"
        # The v3 radius search is capped at 25 km, which misses metropolitan stations around
        # several host cities. Fall back to a bounding box (~55 km) before giving up.
        if not data.get("results") and radius_m > 25000:
            d = round(radius_m / 111000.0, 3)
            q2 = urllib.parse.urlencode({
                "bbox": f"{lon - d:.3f},{lat - d:.3f},{lon + d:.3f},{lat + d:.3f}", "limit": limit})
            data = _fetch(q2)
            search = f"bbox +/-{d:.2f} deg (~{radius_m / 1000:.0f} km)"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return _error("openaq", venue, e)

    locs = []
    for r in data.get("results", []):
        coords = r.get("coordinates") or {}
        slat, slon = coords.get("latitude"), coords.get("longitude")
        locs.append({
            "id": r.get("id"), "name": r.get("name"),
            "provider": (r.get("provider") or {}).get("name"),
            # Keep sensor ids: the /latest endpoint identifies readings by sensorsId only.
            "sensors": [{"id": s.get("id"),
                         "parameter": ((s.get("parameter") or {}).get("name") or "")}
                        for s in (r.get("sensors") or [])],
            "distance_km": (haversine_km(lat, lon, slat, slon)
                            if isinstance(slat, (int, float)) and isinstance(slon, (int, float))
                            else None),
            "grade": provider_grade((r.get("provider") or {}).get("name")),
            "last": (r.get("datetimeLast") or {}).get("utc")})
    locs.sort(key=lambda l: (l["distance_km"] is None, l["distance_km"]))
    return {"source": "openaq", "venue": venue, "retrieved_at": _now(), "kind": "station_index",
            "locations": locs, "detail": {"search": search},
            "attribution": ATTRIBUTION["openaq"]}


def openaq_latest(venue: str, lat: float, lon: float, radius_m: int = 50000,
                  api_key: str | None = None, timeout: float = 30.0,
                  max_age_hours: float = 24.0) -> dict:
    """Latest station values near the venue, averaged across stations per pollutant.

    Only readings newer than `max_age_hours` are used. A station that stopped publishing still
    answers /latest with its final measurement, so without this an abandoned feed is reported as
    current air quality: the CETESB stations around Sao Paulo last reached OpenAQ in April 2023.
    """
    key = api_key or os.environ.get("OPENAQ_API_KEY")
    idx = openaq_locations(venue, lat, lon, radius_m, key, timeout=timeout)
    if idx.get("status") == "error":
        return idx
    base = {"source": "openaq", "venue": venue, "retrieved_at": _now(), "kind": "station",
            "units": "ug/m3", "attribution": ATTRIBUTION["openaq"]}
    if not idx["locations"]:
        return {**base, "status": "no_stations", "values": {},
                "detail": {"radius_m": radius_m, "search": (idx.get("detail") or {}).get("search")}}

    buckets: dict[str, list[float]] = {p: [] for p in POLLUTANTS}
    used, stale, latest_time, max_km, grades = [], [], None, None, set()
    for loc in idx["locations"]:
        age = _age_hours(loc.get("last"))
        if age is None or age > max_age_hours:
            stale.append({"name": loc["name"], "last": loc.get("last"),
                          "age_hours": None if age is None else round(age, 1)})
            continue
        # /latest returns {sensorsId, value, datetime} with no parameter name, so resolve the
        # sensor ids from the station index. Without this every reading is silently dropped.
        sensor_param = {s["id"]: _canon(s["parameter"]) for s in loc.get("sensors", [])
                        if s.get("id") is not None}
        try:
            data = _get(f"{OPENAQ}/locations/{loc['id']}/latest", headers={"X-API-Key": key},
                        timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
        contributed = False
        for r in data.get("results", []):
            name = _canon(((r.get("parameter") or {}).get("name") if isinstance(r.get("parameter"), dict)
                           else r.get("parameter")) or sensor_param.get(r.get("sensorsId"), ""))
            val = r.get("value")
            t = (r.get("datetime") or {}).get("utc") if isinstance(r.get("datetime"), dict) else r.get("datetime")
            r_age = _age_hours(t)
            if r_age is not None and r_age > max_age_hours:
                continue
            if name in buckets and isinstance(val, (int, float)):
                buckets[name].append(float(val))
                contributed = True
                latest_time = max(filter(None, [latest_time, t])) if (latest_time or t) else None
        if contributed:
            used.append({"name": loc["name"], "provider": loc.get("provider"),
                         "grade": loc.get("grade"), "distance_km": loc.get("distance_km")})
            grades.add(loc.get("grade"))
            if isinstance(loc.get("distance_km"), (int, float)):
                max_km = max(max_km or 0, loc["distance_km"])

    values = {p: round(sum(v) / len(v), 1) for p, v in buckets.items() if v}
    if not values:
        status = "all_stale" if stale else "no_values"
    elif grades and grades <= {"low_cost"}:
        status = "low_cost_only"
    else:
        status = None
    return {**base, "observed_at": latest_time, "values": values, "status": status,
            "detail": {"stations_used": used, "n_used": len(used),
                       "stations_stale": stale[:10], "n_stale": len(stale),
                       "radius_m": radius_m, "max_age_hours": max_age_hours,
                       "furthest_station_km": max_km,
                       "search": (idx.get("detail") or {}).get("search"),
                       "note": "mean across current stations within the radius; station siting "
                               "varies, and low-cost sensors are not reference-grade"}}


# --------------------------------------------------------------------------- WAQI
def waqi_nearest(venue: str, lat: float, lon: float, token: str | None = None,
                 timeout: float = 30.0, max_station_km: float = 50.0) -> dict:
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
    # geo:lat;lon returns the nearest station at ANY distance, so a city with no station of its
    # own silently receives another city's air. Measure the distance and flag it.
    geo = (d.get("city") or {}).get("geo") or []
    station_km = (haversine_km(lat, lon, geo[0], geo[1])
                  if len(geo) == 2 and all(isinstance(g, (int, float)) for g in geo) else None)
    far = station_km is not None and station_km > max_station_km
    pm25_aqi = iaqi.get("pm25")
    return {"source": "waqi", "venue": venue, "retrieved_at": _now(),
            "observed_at": (d.get("time") or {}).get("iso"), "kind": "station", "units": "aqi",
            "status": "far_station" if far else None,
            "values": {"pm2_5": pm25_aqi, "pm10": iaqi.get("pm10"),
                       "no2": iaqi.get("no2"), "o3": iaqi.get("o3")},
            "values_ugm3_est": {"pm2_5": pm25_from_aqi(pm25_aqi)},
            "detail": {"aqi": d.get("aqi"), "station": (d.get("city") or {}).get("name"),
                       "station_km": station_km, "max_station_km": max_station_km,
                       "attributions": [a.get("name") for a in d.get("attributions", [])],
                       "note": "AQI sub-indices (US EPA scale), not concentrations; "
                               "values_ugm3_est inverts the EPA PM2.5 breakpoints so the reading "
                               "can be compared with WHO guideline levels"
                               + (f". Nearest station is {station_km} km away, beyond the "
                                  f"{max_station_km} km limit: it does not describe this venue."
                                  if far else "")},
            "attribution": ATTRIBUTION["waqi"]}


FETCHERS = {"openmeteo": open_meteo_current, "openaq": openaq_latest, "waqi": waqi_nearest}


def snapshot(venue: str, lat: float, lon: float, sources: list[str], **kw) -> list[dict]:
    out = []
    for s in sources:
        fn = FETCHERS.get(s)
        out.append(fn(venue, lat, lon, **kw) if fn else _error(s, venue, "unknown source"))
    return out
