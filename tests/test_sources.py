"""Source adapters: response parsing, normalisation and failure handling.
All tests run offline; HTTP is replaced with canned payloads."""
import json

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
    assert r["detail"]["n_stations"] == 1 and "CETESB" not in r["values"]
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
