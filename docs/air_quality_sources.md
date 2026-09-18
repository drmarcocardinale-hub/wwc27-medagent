# Where the air-quality data comes from, and how to keep pulling it

Three kinds of source are useful for a tournament, and they answer different questions.

| | Source | What you get | Key | Cadence that makes sense | Caveat |
|---|---|---|---|---|---|
| **1. Operational (automated)** | **Open-Meteo air-quality API** (CAMS) | PM2.5, PM10, NO₂, O₃, CO, dust; hourly; history from 2013 and a 5-day forecast; every host city | none for non-commercial use | daily pull, plus a forecast check before each match | model grid values (~40 km globally), not a station; attribution to CAMS and Open-Meteo required |
| **1b. Station data (automated)** | **OpenAQ v3** | measurements from official networks that publish openly, by station | free key, header `X-API-Key` ([register](https://explore.openaq.org/register)) | daily pull | coverage depends on what each agency publishes — run the `probe` mode first to see what exists near each venue |
| **1c. Station data (automated)** | **WAQI / aqicn.org** | real-time station feeds, including CETESB's ~65 stations in São Paulo state | free token ([request](https://aqicn.org/data-platform/token/)) | daily pull | returns **AQI sub-indices, not µg/m³**; free tier is non-commercial and needs attribution to WAQI and the agency |
| **2. Brazilian reference (manual)** | **IEMA "Plataforma da Qualidade do Ar"** | standardised historical data for 11 states + the Federal District — which covers all eight host states — from 2000, daily and annual | none | once, and again before submission | download per state (Google Drive), so not automatable; this is the dataset WHO uses for Brazil |
| | **CETESB QUALAR** (São Paulo) and **MonitorAr** (Rio) | hourly station data at source | QUALAR needs a free account; MonitorAr is open | monthly, or when you need station-level evidence | the R package [`qualR`](https://docs.ropensci.org/qualR/) already wraps both |
| | State agencies elsewhere | bulletins and reports | — | before travel | FEAM (MG) and FEPAM (RS) publish bulletins; confirm whether IBRAM (DF), INEMA (BA), CPRH (PE) and SEMACE (CE) run networks |
| **3. Research baseline (citable)** | **BRAIN** (Hoinaski et al., *ESSD* 2024, doi:10.5194/essd-16-2385-2024) | modelled hourly air quality for all Brazil at 20 km (4 km in the south), validated against 244 stations | none | one-off | 2019 only; good for a published baseline, not for current conditions |

## What is wired into this repository

`scripts/pull_air_quality.py` handles sources 1, 1b and 1c and normalises them into one record shape.

```bash
python scripts/pull_air_quality.py --mode probe                 # what can each source see near each venue?
python scripts/pull_air_quality.py                              # daily snapshot, all sources
python scripts/pull_air_quality.py --sources openmeteo          # no keys needed
python scripts/pull_air_quality.py --mode climatology --years 3 # June–July history -> air_quality.json
```

Output goes to `wwc27_medagent/data/airq_archive/`: `YYYY-MM.jsonl` (append-only) and `latest.json`. Failed pulls are written too, with the reason, so gaps are visible rather than silent.

Keys are read from the environment:

```bash
export OPENAQ_API_KEY=...    # optional
export WAQI_TOKEN=...        # optional
export AIRQ_SOURCES=openmeteo,openaq,waqi   # what get_air_quality(live=True) uses
```

## Pulling regularly without running a server

`.github/workflows/air-quality.yml` runs the snapshot every day at 09:10 UTC (06:10 in Brazil) and commits the new readings. Add `OPENAQ_API_KEY` and `WAQI_TOKEN` as repository secrets to include the station sources; without them the workflow still records Open-Meteo. You can also trigger it by hand from the Actions tab and choose the mode.

Alternatives if you would rather not use Actions: `cron` on any always-on machine (`10 6 * * * cd /path/to/wwc27-medagent && python scripts/pull_air_quality.py`), or a scheduled task in Claude that runs the same command.

## Reading the numbers

- Compare µg/m³ against the WHO 2021 guideline levels (PM2.5 15 µg/m³ over 24 h; PM10 45; NO₂ 25; ozone 100 µg/m³ over 8 h) — the agent's planning bands do this.
- Never mix WAQI AQI values into a µg/m³ series; the archive records `units` per record for this reason.
- A model grid cell or a city-centre station may not describe a training ground beside a motorway. When a session's air quality matters clinically, a portable monitor at the pitch is the only way to know.
