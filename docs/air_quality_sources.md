# Where the air-quality data comes from, and how to keep pulling it

Three kinds of source are useful for a tournament, and they answer different questions.

| | Source | What you get | Key | Cadence that makes sense | Caveat |
|---|---|---|---|---|---|
| **1. Operational (automated)** | **Open-Meteo air-quality API** (CAMS) | PM2.5, PM10, NO₂, O₃, CO, dust; hourly; history from 2013 and a 5-day forecast; every host city | none for non-commercial use | twice-daily pull, plus a forecast check before each match | model grid values (~40 km globally), not a station; attribution to CAMS and Open-Meteo required |
| **1b. Station data (automated)** | **OpenAQ v3** | measurements from official networks that publish openly, by station | free key, header `X-API-Key` ([register](https://explore.openaq.org/register)) | twice-daily pull | coverage depends on what each agency publishes — run the `probe` mode first to see what exists near each venue |
| **1c. Station data (automated)** | **WAQI / aqicn.org** | real-time station feeds, including CETESB's ~65 stations in São Paulo state | free token ([request](https://aqicn.org/data-platform/token/)) | twice-daily pull | returns **AQI sub-indices, not µg/m³**; free tier is non-commercial and needs attribution to WAQI and the agency |
| **2. Brazilian reference (manual)** | **IEMA "Plataforma da Qualidade do Ar"** | standardised historical data for 11 states + the Federal District — which covers all eight host states — from 2000, daily and annual | none | once, and again before submission | download per state (Google Drive), so not automatable; this is the dataset WHO uses for Brazil |
| | **CETESB QUALAR** (São Paulo) and **MonitorAr** (Rio) | hourly station data at source | QUALAR needs a free account; MonitorAr is open | monthly, or when you need station-level evidence | the R package [`qualR`](https://docs.ropensci.org/qualR/) already wraps both |
| | State agencies elsewhere | bulletins and reports | — | before travel | FEAM (MG) and FEPAM (RS) publish bulletins; confirm whether IBRAM (DF), INEMA (BA), CPRH (PE) and SEMACE (CE) run networks |
| **3. Research baseline (citable)** | **BRAIN** (Hoinaski et al., *ESSD* 2024, doi:10.5194/essd-16-2385-2024) | modelled hourly air quality for all Brazil at 20 km (4 km in the south), validated against 244 stations | none | one-off | 2019 only; good for a published baseline, not for current conditions |

## Better sources, found 18 September 2026

The first authenticated probe showed that OpenAQ and WAQI between them cover two of the eight host cities. These were found while looking for something better. The short version: **the data exists, but almost none of it reaches the international aggregators.**

| Source | Covers | Access | Verdict |
|---|---|---|---|
| **MonitorAr** — Sistema Nacional de Gestão da Qualidade do Ar (MMA) — [dataset](https://dados.mma.gov.br/dataset/ar-puro-monitorar), [live site](https://monitorar.mma.gov.br/) | National; aggregates the state agencies' official stations | Annual CSV/ZIP per year, 2022–2025, **CC BY**. Live site + phone app, no documented API | **Best available.** Reference-grade measurements for the tournament window. The download host is not on our egress allowlist, so it is a manual download — see below |
| **Porto Alegre SMAMUS** — [dashboard](https://prefeitura.poa.br/qualidade-do-ar/) | Porto Alegre: 5 fixed + 1 mobile station, PM2.5, PM10, O₃, NO₂, SO₂, CO, since March 2025 | Real-time dashboard only; nothing in the city's [open-data portal](https://dadosabertos.poa.br/) | Fills a gap OpenAQ cannot. Needs a data request to SMAMUS, or scraping |
| **ProAr BH** — [programme](https://prefeitura.pbh.gov.br/meio-ambiente/proar) | Belo Horizonte: municipal "hyperlocal" sensor network, IQAr per CONAMA 491/2018 and 506/2024 | Power BI dashboard; no open feed | Useful for situational awareness. Sensor grade unclear — treat as indicative, not reference |
| **CETESB QUALAR** — [catalogue](https://cetesb.sp.gov.br/catalogo-de-dados-abertos/), [map](https://servicos.cetesb.sp.gov.br/qa) | São Paulo state, ~65 stations | Free account; the [`qualR`](https://docs.ropensci.org/qualR/) R package and community scrapers automate it | The right answer for São Paulo, whose OpenAQ feed stopped in April 2023 |
| **IBRAM (DF)** — [reports](https://www.ibram.df.gov.br/programa-de-monitoramento-da-qualidade-do-ar-do-df/) | Brasília | Monthly PDF reports | Too coarse and too slow for operational use; fine as background |
| **CPRH (PE)**, **SEMACE (CE)**, **INEMA (BA)** | Recife, Fortaleza, Salvador | Agency pages, mostly bulletins | Confirm station lists directly with each agency before the tournament |
| **IQAir / AirVisual** — [API docs](https://api-docs.iqair.com/) | Has city pages for Brasília, Recife and Fortaleza | Free key; `/nearest_city` on the free tier, `/nearest_station` needs a paid plan. Returns µg/m³ and US AQI | A practical fallback for a team's own use. Check the licence before redistributing values in an openly licensed repository |

### Using MonitorAr for a measured climatology

This is the one change that materially improves the article: it replaces modelled grid values with real instruments for the tournament window.

```bash
# 1. Download the yearly files by hand from
#    https://dados.mma.gov.br/dataset/ar-puro-monitorar   (2022-2025, CC BY)
# 2. Put them in one folder, then:
python scripts/build_monitorar_climatology.py --inspect data/monitorar   # confirm the schema
python scripts/build_monitorar_climatology.py data/monitorar             # build
```

It pools 1 June – 31 July across years per host city and writes `climatology_stations` into `air_quality.json`, keeping the modelled CAMS `climatology` separately so the provenance of each number stays explicit. Cite MonitorAr and the MMA.

## What is wired into this repository

`scripts/pull_air_quality.py` handles sources 1, 1b and 1c and normalises them into one record shape.

```bash
python scripts/pull_air_quality.py --mode probe                 # what can each source see near each venue?
python scripts/pull_air_quality.py                              # one snapshot now, all sources
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

`.github/workflows/air-quality.yml` runs the snapshot **twice a day** — 09:10 and 20:10 UTC, which is 06:10 and 17:10 in Brazil (UTC−3 all year) — and commits the new readings. The morning run informs the day's training; the late-afternoon run covers evening sessions and kick-offs. You can also trigger it by hand from the Actions tab and choose the mode.

### Adding the API keys as repository secrets

The workflow reads `OPENAQ_API_KEY` and `WAQI_TOKEN` from GitHub secrets. Without them it still records Open-Meteo, which needs no key.

1. Get the keys: OpenAQ — register at <https://explore.openaq.org/register> and copy the key from your account page. WAQI — request a token at <https://aqicn.org/data-platform/token/> and confirm the email.
2. In the GitHub repository, go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Name it exactly `OPENAQ_API_KEY`, paste the key into *Secret*, and click **Add secret**. Repeat for `WAQI_TOKEN`.
4. Check it worked: **Actions → air-quality pull → Run workflow**, choose mode `probe`, and read the run summary. Station sources appear instead of "no OPENAQ_API_KEY set".

Names are case-sensitive, and the values are write-only afterwards — GitHub will show the name but never the value, so store the keys in your password manager too. To change one later, open the secret and choose **Update**.

### Alternatives to GitHub Actions

- `cron` on any always-on machine, twice a day:
  ```
  10 6,17 * * * cd /path/to/wwc27-medagent && /usr/bin/python3 scripts/pull_air_quality.py >> pull.log 2>&1
  ```
  Put the keys in that machine's environment (for example in `~/.profile`, or as `OPENAQ_API_KEY=... WAQI_TOKEN=... ` at the start of the cron line).
- A scheduled task in Claude that runs the same command.

## Reading the numbers

- Compare µg/m³ against the WHO 2021 guideline levels (PM2.5 15 µg/m³ over 24 h; PM10 45; NO₂ 25; ozone 100 µg/m³ over 8 h) — the agent's planning bands do this.
- Never mix WAQI AQI values into a µg/m³ series; the archive records `units` per record for this reason.
- A model grid cell or a city-centre station may not describe a training ground beside a motorway. When a session's air quality matters clinically, a portable monitor at the pitch is the only way to know.
