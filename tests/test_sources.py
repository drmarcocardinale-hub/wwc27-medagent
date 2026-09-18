"""Source adapters: response parsing, normalisation and failure handling.
All tests run offline; HTTP is replaced with canned payloads."""
import json
from datetime import datetime, timezone

import pytest

from wwc27_medagent import core, sources

OPEN_METEO_CURRENT = {"current": {"time": "2027-06-24T15:00", "pm2_5": 18.4, "pm10": 31.2,
                                  "nitrogen_dioxide": 22.0, "ozone": 71.5,
                                  "carbon_monoxide": 210.0, "dust": 1.2}}
OPEN_METEO_RANGE = {"hourly": {"time": ["2026-06-01T00:00", "2026-06-01T01:00"],
                               "pm2_5": [10.0, 12.0], "pm10": [20.0, 22.0],
                               "nitrogen_dioxide": [15.0, 16.0], "ozone": [40.0, 44.0]}}
OPENAQ_LOCATIONS = {"results": [
    {"id": 101, "name": "Parque Dom Pedro II", "provider": {"name": "CETESB"},
     "sensors": [{"parameter": {"name": "pm25"}}, {"parameter": {"name": "o3"}}],
     "datetimeLast": {"utc": "2027-06-24T18:00:00Z"}}]}
OPENAQ_LATEST = {"results": [
    {"parameter": {"name": "pm25"}, "value": 21.0, "datetime": {"utc": "2027-06-24T18:00:00Z"}},
    {"parameter": {"name": "o3"}, "value": 64.0, "datetime": {"utc": "2027-06-24T18:00:00Z"}}]}
WAQI_FEED = {"status": "ok", "data": {"aqi": 62, "time": {"iso": "2027-06-24T15:00:00-03:00"},
                                      "city": {"name": "Sao Paulo, Cerqueira Cesar"},
                                      "iaqi": {"pm25": {"v": 62}, "o3": {"v": 18}},
                                      "attributions": [{"name": "CETESB"}]}}


@pytest.fixture
def fake_http(monkeypatch):
    calls = []

    def route(url, headers=None, timeout=30.0):
        calls.append(url)
        if "air-quality-api.open-meteo.com" in url:
            return OPEN_METEO_RANGE if "hourly=" in url else OPEN_METEO_CURRENT
        if "/v3/locations/" in url and url.endswith("/latest"):
            return OPENAQ_LATEST
        if "/v3/locations" in url:
            return OPENAQ_LOCATIONS
        if "api.waqi.info" in url:
            return WAQI_FEED
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(sources, "_get", route)
    return calls


def test_open_meteo_current_normalised(fake_http):
    r = sources.open_meteo_current("sao_paulo", -23.5, -46.6)
    assert r["units"] == "ug/m3" and r["kind"] == "model_forecast"
    assert r["values"] == {"pm2_5": 18.4, "pm10": 31.2, "no2": 22.0, "o3": 71.5}
    assert "CAMS" in r["attribution"] and r["observed_at"] == "2027-06-24T15:00"


def test_open_meteo_range_series(fake_http):
    r = sources.open_meteo_range("recife", -8.0, -35.0, "2026-06-01", "2026-07-31")
    assert r["kind"] == "model_archive" and len(r["time"]) == 2
    assert r["series"]["pm2_5"] == [10.0, 12.0]
    assert "start_date=2026-06-01" in fake_http[0] and "end_date=2026-07-31" in fake_http[0]


def test_openaq_latest_averages_stations(fake_http, monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key")
    r = sources.openaq_latest("sao_paulo", -23.5, -46.6)
    assert r["kind"] == "station" and r["units"] == "ug/m3"
    assert r["values"]["pm2_5"] == 21.0 and r["values"]["o3"] == 64.0
    assert r["detail"]["n_used"] == 1 and "CETESB" not in r["values"]
    assert any("coordinates=-23.5" in u for u in fake_http)


def test_openaq_without_key_is_reported_not_raised(monkeypatch):
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    r = sources.openaq_latest("recife", -8.0, -35.0)
    assert r["status"] == "error" and "OPENAQ_API_KEY" in r["detail"]


def test_waqi_returns_aqi_units_with_warning(fake_http, monkeypatch):
    monkeypatch.setenv("WAQI_TOKEN", "tok")
    r = sources.waqi_nearest("sao_paulo", -23.5, -46.6)
    assert r["units"] == "aqi" and r["values"]["pm2_5"] == 62
    assert "not concentrations" in r["detail"]["note"]
    assert r["detail"]["station"].startswith("Sao Paulo")


def test_waqi_api_error_status(monkeypatch):
    monkeypatch.setenv("WAQI_TOKEN", "tok")
    monkeypatch.setattr(sources, "_get", lambda *a, **k: {"status": "error", "data": "Invalid key"})
    r = sources.waqi_nearest("rio_de_janeiro", -22.9, -43.2)
    assert r["status"] == "error" and "Invalid key" in r["detail"]


def test_network_failure_is_recorded(monkeypatch):
    def boom(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr(sources, "_get", boom)
    r = sources.open_meteo_current("salvador", -12.9, -38.5)
    assert r["status"] == "error" and "no route" in r["detail"]


def test_snapshot_returns_one_record_per_source(fake_http, monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "k")
    monkeypatch.setenv("WAQI_TOKEN", "t")
    recs = sources.snapshot("sao_paulo", -23.5, -46.6, ["openmeteo", "openaq", "waqi", "nonsense"])
    assert [r["source"] for r in recs] == ["openmeteo", "openaq", "waqi", "nonsense"]
    assert recs[-1]["status"] == "error"


def test_agent_live_lookup_uses_sources(fake_http, monkeypatch):
    monkeypatch.setenv("AIRQ_SOURCES", "openmeteo")
    aq = core.air_quality("Sao Paulo", live=True)
    assert aq["live"]["status"] == "ok" and aq["live"]["pm2_5"] == 18.4
    assert aq["live"]["planning_band"]["band"] == "moderate"


def test_agent_live_lookup_reports_unavailable(monkeypatch):
    monkeypatch.setattr(sources, "_get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setenv("AIRQ_SOURCES", "openmeteo")
    aq = core.air_quality("Recife", live=True)
    assert aq["live"]["status"] == "unavailable" and "advice" in aq["live"]


def test_pull_script_snapshot_writes_archive(fake_http, monkeypatch, tmp_path):
    import importlib.util
    from pathlib import Path

    script = Path(core.__file__).parents[1] / "scripts" / "pull_air_quality.py"
    spec = importlib.util.spec_from_file_location("pull_air_quality", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ARCHIVE", tmp_path)

    args = type("A", (), {"sources": ["openmeteo"], "venues": ["fortaleza"], "timeout": 5})()
    assert mod.do_snapshot(args) == 0
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert len(latest["records"]) == 1
    assert latest["records"][0]["city"] == "Fortaleza"
    assert latest["records"][0]["planning_band"] == "moderate"   # 18.4 ug/m3
    assert list(tmp_path.glob("*.jsonl"))


def test_pull_script_records_failures_and_returns_nonzero(monkeypatch, tmp_path):
    import importlib.util
    from pathlib import Path

    script = Path(core.__file__).parents[1] / "scripts" / "pull_air_quality.py"
    spec = importlib.util.spec_from_file_location("pull_air_quality", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ARCHIVE", tmp_path)
    monkeypatch.setattr(mod.sources, "_get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))

    args = type("A", (), {"sources": ["openmeteo"], "venues": ["recife"], "timeout": 1})()
    assert mod.do_snapshot(args) == 1
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["records"][0]["status"] == "error"


# ------------------------------------------------- regression: real-world pull, 18 Sep 2026
# The first live run exposed three defects. Each is pinned here.

def test_openaq_latest_resolves_parameters_from_sensor_ids(monkeypatch):
    """OpenAQ v3 /latest identifies readings by sensorsId only, with no parameter name.

    Matching on a missing `parameter` field silently dropped every value, so all eight cities
    reported pm2.5=None while appearing to succeed.
    """
    locations = {"results": [{
        "id": 7, "name": "Centro", "provider": {"name": "CETESB"},
        "coordinates": {"latitude": -23.55, "longitude": -46.63},
        "sensors": [{"id": 101, "parameter": {"name": "pm25"}},
                    {"id": 102, "parameter": {"name": "o3"}}],
        "datetimeLast": {"utc": "2026-09-18T12:00:00Z"}}]}
    latest = {"results": [{"sensorsId": 101, "value": 12.4, "datetime": {"utc": "2026-09-18T12:00:00Z"}},
                          {"sensorsId": 102, "value": 40.0, "datetime": {"utc": "2026-09-18T12:00:00Z"}}]}

    def fake_get(url, headers=None, timeout=30.0, **kw):
        return latest if "/latest" in url else locations

    monkeypatch.setattr(sources, "_get", fake_get)
    rec = sources.openaq_latest("sao_paulo", -23.55, -46.63, api_key="k")
    assert rec["values"]["pm2_5"] == 12.4
    assert rec["values"]["o3"] == 40.0
    assert rec["status"] is None
    assert rec["detail"]["furthest_station_km"] is not None


def test_openaq_falls_back_to_bbox_when_radius_finds_nothing(monkeypatch):
    """The v3 radius search is capped at 25 km, which returned no_stations for four host cities."""
    calls = []

    def fake_get(url, headers=None, timeout=30.0, **kw):
        calls.append(url)
        if "bbox" in url:
            return {"results": [{"id": 1, "name": "Far station", "provider": {"name": "X"},
                                 "coordinates": {"latitude": -15.9, "longitude": -47.9},
                                 "sensors": [{"id": 9, "parameter": {"name": "pm25"}}],
                                 "datetimeLast": {"utc": "2026-09-18T12:00:00Z"}}]}
        return {"results": []}

    monkeypatch.setattr(sources, "_get", fake_get)
    idx = sources.openaq_locations("brasilia", -15.78, -47.93, radius_m=50000, api_key="k")
    assert any("bbox" in c for c in calls)
    assert len(idx["locations"]) == 1
    assert "bbox" in idx["detail"]["search"]


def test_waqi_flags_a_station_that_is_not_near_the_venue(monkeypatch):
    """geo: lookup returns the nearest station at any distance.

    Salvador and Recife (677 km apart) both received the same feed, so a single distant station
    was being reported as two cities' air quality.
    """
    feed = {"status": "ok", "data": {
        "aqi": 30, "iaqi": {"pm25": {"v": 30}},
        "city": {"name": "Somewhere far", "geo": [-23.55, -46.63]},   # Sao Paulo
        "time": {"iso": "2026-09-18T12:00:00-03:00"}, "attributions": []}}
    monkeypatch.setattr(sources, "_get", lambda *a, **k: feed)

    rec = sources.waqi_nearest("recife", -8.0476, -34.8770, token="t")
    assert rec["status"] == "far_station"
    assert rec["detail"]["station_km"] > 1000
    assert "does not describe this venue" in rec["detail"]["note"]

    near = sources.waqi_nearest("sao_paulo", -23.55, -46.63, token="t")
    assert near["status"] is None
    assert near["detail"]["station_km"] < 5


def test_waqi_aqi_is_converted_before_comparison_with_who_levels(monkeypatch):
    """WAQI returns AQI sub-indices. Treating AQI 65 as 65 ug/m3 overstates PM2.5 ~4x."""
    feed = {"status": "ok", "data": {
        "aqi": 65, "iaqi": {"pm25": {"v": 65}},
        "city": {"name": "Brasilia", "geo": [-15.78, -47.93]},
        "time": {"iso": "2026-09-18T12:00:00-03:00"}, "attributions": []}}
    monkeypatch.setattr(sources, "_get", lambda *a, **k: feed)
    rec = sources.waqi_nearest("brasilia", -15.78, -47.93, token="t")
    assert rec["units"] == "aqi"
    assert rec["values"]["pm2_5"] == 65
    assert rec["values_ugm3_est"]["pm2_5"] == pytest.approx(16.6, abs=0.2)

    assert sources.pm25_from_aqi(50) == pytest.approx(9.0, abs=0.1)
    assert sources.pm25_from_aqi(100) == pytest.approx(35.4, abs=0.1)
    assert sources.pm25_from_aqi(0) == 0.0
    assert sources.pm25_from_aqi(None) is None
    assert sources.pm25_from_aqi(-5) is None


def test_transient_failure_is_retried_once(monkeypatch):
    """Brasilia errored while the other seven cities succeeded - a transient upstream failure."""
    state = {"n": 0}

    def flaky(req, timeout=None):
        state["n"] += 1
        raise OSError("transient" if state["n"] == 1 else "still down")

    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    monkeypatch.setattr(sources.urllib.request, "urlopen", flaky)
    with pytest.raises(OSError):
        sources._get("https://example.invalid/x")
    assert state["n"] == 2, "the request should have been attempted twice"


# ------------------------------------- regression: live probe, 18 Sep 2026 (real API responses)

def _loc(name, provider, sensors, last, lat=-23.55, lon=-46.63):
    return {"id": abs(hash(name)) % 10000, "name": name, "provider": {"name": provider},
            "coordinates": {"latitude": lat, "longitude": lon},
            "sensors": [{"id": i, "parameter": {"name": p}} for i, p in enumerate(sensors, 1)],
            "datetimeLast": {"utc": last}}


def test_abandoned_station_feed_is_not_reported_as_current_air_quality(monkeypatch):
    """The CETESB stations around Sao Paulo last reached OpenAQ on 2026-04-05... of 2023.

    /latest still returns those final measurements, so without an age check a three-year-old
    reading is averaged and presented as today's PM2.5 for the largest host city.
    """
    locations = {"results": [_loc("Itaim Paulista", "Sao Paulo CETESB",
                                  ["no2", "o3", "pm10", "pm25"], "2023-04-05T20:00:00Z")]}
    latest = {"results": [{"sensorsId": 4, "value": 88.0,
                           "datetime": {"utc": "2023-04-05T20:00:00Z"}}]}
    monkeypatch.setattr(sources, "_get",
                        lambda url, **kw: latest if "/latest" in url else locations)

    rec = sources.openaq_latest("sao_paulo", -23.55, -46.63, api_key="k")
    assert rec["values"] == {}, "a 2023 reading must not become today's value"
    assert rec["status"] == "all_stale"
    assert rec["detail"]["n_stale"] == 1
    assert rec["detail"]["stations_stale"][0]["name"] == "Itaim Paulista"


def test_current_station_is_used_and_graded(monkeypatch):
    """Rio's Presidente Vargas reported within the hour and measures PM2.5."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    locations = {"results": [_loc("Presidente Vargas", "Rio City Hall", ["pm10", "pm25"], now,
                                  -22.906, -43.176)]}
    latest = {"results": [{"sensorsId": 2, "value": 11.2, "datetime": {"utc": now}}]}
    monkeypatch.setattr(sources, "_get",
                        lambda url, **kw: latest if "/latest" in url else locations)

    rec = sources.openaq_latest("rio_de_janeiro", -22.9068, -43.1729, api_key="k")
    assert rec["values"]["pm2_5"] == 11.2
    assert rec["status"] is None
    assert rec["detail"]["stations_used"][0]["grade"] == "reference"


def test_low_cost_only_coverage_is_flagged(monkeypatch):
    """Salvador's only station is an AirGradient unit; Fortaleza's is a HabitatMap test device.

    Low-cost sensors are usable for trend but are not reference instruments, so a venue covered
    only by one must not look equivalent to a government network.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    locations = {"results": [_loc("Parque Vida Nova, Caji", "AirGradient", ["pm1", "pm25"], now,
                                  -12.90, -38.40)]}
    latest = {"results": [{"sensorsId": 2, "value": 6.3, "datetime": {"utc": now}}]}
    monkeypatch.setattr(sources, "_get",
                        lambda url, **kw: latest if "/latest" in url else locations)

    rec = sources.openaq_latest("salvador", -12.9777, -38.5016, api_key="k")
    assert rec["values"]["pm2_5"] == 6.3
    assert rec["status"] == "low_cost_only"
    assert sources.provider_grade("HabitatMap") == "low_cost"
    assert sources.provider_grade("Sao Paulo CETESB") == "reference"
    assert sources.provider_grade(None) == "unknown"


def test_station_that_never_reported_is_excluded(monkeypatch):
    """Fortaleza's '211004_teste_modo_fixo' (HabitatMap) has last=None - a test device."""
    locations = {"results": [_loc("211004_teste_modo_fixo", "HabitatMap", ["pm25"], None)]}
    monkeypatch.setattr(sources, "_get", lambda url, **kw: locations)
    rec = sources.openaq_latest("fortaleza", -3.7319, -38.5267, api_key="k")
    assert rec["values"] == {}
    assert rec["status"] == "all_stale"


def test_waqi_distances_from_the_live_probe_are_all_rejected_except_sao_paulo():
    """Seven of eight venues were served a station 200-1800 km away."""
    cases = [("rio", -22.9068, -43.1729, -22.816, -45.192, True),
             ("sao_paulo", -23.5505, -46.6333, -23.540, -46.455, False),
             ("fortaleza", -3.7319, -38.5267, 4.846, -52.331, True)]   # French Guiana
    for name, vlat, vlon, slat, slon, should_reject in cases:
        km = sources.haversine_km(vlat, vlon, slat, slon)
        assert (km > 50) is should_reject, f"{name}: {km} km"
