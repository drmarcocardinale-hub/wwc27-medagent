# WWC27-MedAgent

[![tests](https://github.com/drmarcocardinale-hub/wwc27-medagent/actions/workflows/tests.yml/badge.svg)](https://github.com/drmarcocardinale-hub/wwc27-medagent/actions/workflows/tests.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22832165.svg)](https://doi.org/10.5281/zenodo.22832165)

WWC27-MedAgent is a **paper agent** for the Current Opinion *"Sports Medicine and Science Considerations to Maximise Preparation for the FIFA Women's World Cup Brazil 2027: From Static Evidence to a Living Agent"* (Cardinale & Geertsema; submitted to *Sports Medicine*). It follows the Paper2Agent model (Miao et al., *Nature* 2026, doi:10.1038/s41586-026-11044-y). The article's tables, decision tools and evidence base are packaged as a **Model Context Protocol (MCP) server**, so any MCP-compatible AI assistant can answer practitioners' questions from them in plain language, with sources.

> **Decision support only.** Outputs summarise published evidence and climate normals. They do not replace clinical judgement, on-site WBGT measurement or current public-health advice. Do not enter identifiable player data.

## What it exposes

| Type | Name | Purpose |
|---|---|---|
| Tool | `get_venue_profile` | June/July climate normals, elevation, indicative sWBGT and heat band, yellow-fever guidance by host city |
| Tool | `estimate_heat_risk` | Indicative sWBGT from a forecast temperature and humidity; FIFA/FIFPRO reference bands; luteal-phase note |
| Tool | `calculate_travel_burden` | Great-circle legs and climate transitions for an itinerary |
| Tool | `build_screening_checklist` | Phase × domain checklist (Table 2), with venue-specific actions |
| Tool | `get_air_quality` | Typical pollution sources and June–July pattern per host city, the state monitoring agency, WHO 2021 guideline levels and Brazil's standards; optional live concentrations from the Open-Meteo (CAMS) API |
| Tool | `plan_respiratory_care` | PM2.5 planning band with session advice, plus asthma/EIB screening, management and the 2026 anti-doping limits for inhaled beta-2 agonists |
| Tool | `list_air_quality_sources` | Where air-quality data for a city can actually be obtained, best source first: the automated APIs and the state/municipal agency portals |
| Tool | `find_evidence` | Search of the curated, source-linked evidence table; replies "I don't know" when a question is out of scope |
| Tool | `tournament_facts` | Dates and format |
| Resource | `wwc27://manuscript`, `wwc27://table1-venues`, `wwc27://table2-screening`, `wwc27://air-quality`, `wwc27://evidence`, `wwc27://references`, `wwc27://changelog` | Machine-readable article content |
| Prompt | `pre_tournament_medical_plan`, `venue_briefing` | Step-by-step workflows that call the tools in order |

## Install and test

```bash
git clone https://github.com/drmarcocardinale-hub/wwc27-medagent.git && cd wwc27-medagent
pip install -e ".[test]"
pytest -q                          # 92 tests: source values, computations, refusal, MCP registration, benchmark integrity
python benchmark/run_tool_check.py # tool-layer benchmark check
```

## Where to use it

| | Link | Needs |
|---|---|---|
| **Read the tables in a browser** | <https://drmarcocardinale-hub.github.io/wwc27-medagent/> | nothing |
| **Use it as an AI agent, hosted** | Cloud Run endpoint — see [`deploy/cloudrun/`](deploy/cloudrun/README.md) | an MCP client |
| **Run it locally** | `pip install -e .` then the config below | Python 3.10+ |
| **See what it answers, no client** | `python scripts/demo.py` | Python 3.10+ |

The GitHub Pages site (`scripts/build_site.py` &rarr; `docs/`) is generated from the same JSON the
agent serves, and the venue table's simplified WBGT is computed by `core` at build time so the
page and the agent can never disagree. The hosted endpoint deploys to Google Cloud Run with `./deploy/cloudrun/deploy.sh`
(scale-to-zero, stable URL); `scripts/make_space.py` packages the same image for a Hugging Face
Space as an alternative.

## Connect to Claude

**Claude Desktop / Cowork:** add this to `claude_desktop_config.json`:

```json
{ "mcpServers": { "wwc27-medagent": { "command": "wwc27-medagent" } } }
```

**Claude Code:** `claude mcp add wwc27-medagent -- wwc27-medagent`

**Remote (optional):** `wwc27-medagent --http` serves streamable HTTP on port 8000 (set `PORT` to change it). A `Dockerfile` is included for institutional or cloud hosting.

Example questions:
- *"We're based in São Paulo and play in Fortaleza, Recife and Porto Alegre. Draft our pre-tournament medical plan."*
- *"Forecast for our Salvador match is 28 °C and 85% humidity, and three starters are likely luteal. What's the heat band and what should we do?"*
- *"What did the 2023 Women's World Cup show about illness?"*

## Validation benchmark

`benchmark/` contains a 61-item benchmark with four sets:
- 25 reproduction questions;
- 13 application questions;
- 11 open-ended questions, scored by two blinded raters;
- 12 out-of-scope questions.

It also contains the scripts to run the agent against two baselines (the manuscript in the prompt, and closed-book) and to score the results. See [`benchmark/README.md`](benchmark/README.md).

## Air quality: pulling data regularly

City profiles are qualitative (typical sources, June–July pattern, monitoring agency); measurements come from live sources. `scripts/pull_air_quality.py` reads four of them and normalises the records:

| Source | Key | What it gives |
|---|---|---|
| Open-Meteo (CAMS) | none | PM2.5, PM10, NO₂, O₃ for every venue; history from 2013 and a 5-day forecast |
| OpenAQ v3 | free `OPENAQ_API_KEY` | official station measurements, where the agency publishes them |
| WAQI (aqicn.org) | free `WAQI_TOKEN` | real-time station feeds, including CETESB's network (AQI, not µg/m³) |
| Google Air Quality | paid `GOOGLE_AIR_QUALITY_KEY` | µg/m³ at ~500 m for all eight venues, fusing stations, satellite and models; the practical option where no station exists. Needs a billed Google Cloud project |
| IQAir / AirVisual | `IQAIR_API_KEY` | adapter retained, but the free Community plan was not obtainable when tested (18 Sep 2026) |

> **Licences differ.** Open-Meteo, OpenAQ and WAQI values are committed to the archive with attribution. Google and IQAir restrict redistribution and caching, so the puller fetches and prints them but **excludes them from the committed archive** (`--archive-all` overrides this; do not use it in a public repository).

Beyond these four, several host cities publish only through their own agency portal. Those are in the registry too, so the agent can point practitioners at them instead of implying no data exists:

```bash
python scripts/pull_air_quality.py --list-sources   # automated + manual, with coverage and URLs
```

```bash
python scripts/pull_air_quality.py --mode probe                  # what each source sees near each venue
python scripts/pull_air_quality.py                               # daily snapshot -> data/airq_archive/
python scripts/pull_air_quality.py --sources openmeteo           # no keys needed
python scripts/pull_air_quality.py --mode climatology --years 3  # June–July history -> air_quality.json
```

### What open station data actually covers (probed 18 September 2026)

Running `--mode probe` against the live APIs gave a blunt answer: **open station data cannot monitor most host cities.**

| City | OpenAQ stations (50 km) | Current PM2.5? | Nearest WAQI station |
|---|---|---|---|
| Rio de Janeiro | 20 | **Yes** — reference-grade | 207 km ✗ |
| São Paulo | 20 (CETESB) | No — feed stops 5 Apr 2023 | 18 km ✓ |
| Brasília | 0 | No | 580 km ✗ |
| Belo Horizonte | 0 | No | 348 km ✗ |
| Porto Alegre | 0 | No | 814 km ✗ |
| Salvador | 1 (AirGradient) | Low-cost sensor only | 832 km ✗ |
| Recife | 0 | No | 1477 km ✗ |
| Fortaleza | 1 (test device, never reported) | No | 1806 km ✗ |

Only Rio has current reference-grade PM2.5 in OpenAQ. São Paulo's CETESB network is indexed but its readings stopped in April 2023, so current CETESB data must come from QUALAR or WAQI. WAQI's `geo:` lookup returns the nearest station at *any* distance — Fortaleza was served a station in French Guiana — so stations beyond 50 km are rejected rather than reported.

The practical consequence: **modelled CAMS values (Open-Meteo) are the only source covering all eight venues**, and a portable monitor at the training site is the only way to characterise a specific pitch. Coverage changes; re-run the probe before relying on it.

`.github/workflows/air-quality.yml` runs the snapshot twice a day (06:10 and 17:10 Brazil time) and commits the readings, so the archive builds itself. Add `OPENAQ_API_KEY` and `WAQI_TOKEN` as repository secrets to include the station sources. Failed pulls are recorded with their reason instead of being dropped. [`docs/air_quality_sources.md`](docs/air_quality_sources.md) compares these with the Brazilian reference datasets (IEMA, CETESB QUALAR, MonitorAr, BRAIN) and explains how to read the numbers.

## Archiving and citation

The code is on GitHub, and each release is archived on Zenodo with its own DOI (see [`RELEASING.md`](RELEASING.md)). Cite the article and the specific release you used (`CITATION.cff`).

| DOI | Points to |
|---|---|
| [10.5281/zenodo.22832165](https://doi.org/10.5281/zenodo.22832165) | **Concept DOI** — always resolves to the newest version. Cite this when you mean "the living resource". |
| [10.5281/zenodo.22832166](https://doi.org/10.5281/zenodo.22832166) | **Version DOI** for v0.3.2, the release archived at manuscript submission. Cite this to pin exactly what you used. |

## Living-mode curation

1. A curator adds or edits entries in `wwc27_medagent/data/*.json` (and re-runs `scripts/pull_air_quality.py --mode climatology` when air-quality data should be refreshed). Every claim needs a `ref` that resolves to a DOI or URL in `references.json`.
2. Add a matching assertion to `tests/`, regenerate the benchmark (`python benchmark/build_benchmark.py`) and push. GitHub Actions must pass.
3. Bump the version, add an entry to `wwc27_medagent/data/CHANGELOG.md` and publish a GitHub release. Zenodo then archives it automatically.
4. Update triggers are listed in the changelog: new surveillance data, schedule changes and outbreak notices.

## Data governance

The server holds no personal data. Teams that want outputs for individual players should run it locally inside their own governance environment.

## Licence

Code: MIT. Data tables: CC BY 4.0, with attribution to the article and the original sources.
