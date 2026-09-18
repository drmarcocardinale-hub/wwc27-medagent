# WWC27-MedAgent curation log

Each release is tagged, re-tested (`pytest`), and archived. Curators: Marco Cardinale, Celeste Geertsema [confirm].

## 0.5.1 — 2026-09-18
Hosting moved to Google Cloud Run after the Hugging Face free tier refused the Space
(`Quota exceeded for flavor cpu-basic: limit=0` on a correctly configured, single Space).

- **Stateless HTTP mode** (`MCP_STATELESS=1`). Streamable HTTP keeps session state in the instance's memory; an autoscaling host can route a follow-up request to a different instance, which then rejects the unknown session. Stateless mode makes every request self-contained — verified locally: `tools/list` and `tools/call` both succeed with no session header. Stateful remains the default for local use, and the only capability given up is server-initiated messages, which this read-only server does not use.
- **`deploy/cloudrun/`**: a one-command deploy (`deploy.sh`) that builds from the repository Dockerfile with Cloud Build — no local Docker — plus a README explaining each setting and its cost implications. Scale-to-zero, capped at 3 instances.
- **`.dockerignore` / `.gcloudignore`**: the build context drops from the whole repository to 456 kB by excluding git history, tests, the benchmark, the site and the Space bundle.
- The Hugging Face path (`scripts/make_space.py`) is kept and still works; the two hosts run the same image.
- 92 automated tests.

## 0.5.0 — 2026-09-18
Deployment: the agent and its content are now reachable without installing anything.

- **Reader site** (`scripts/build_site.py` → `docs/`, GitHub Pages): host-city table, the eleven-domain screening matrix, all 39 evidence items with searchable source links, air-quality profiles with measured station coverage, and the 49 references — as one self-contained page with no CDN, no fonts and no build step, so it works offline and cannot be broken by a third party. The venue table's simplified WBGT and heat bands are computed by `core` at build time rather than re-implemented in JavaScript, so the page, the agent and the manuscript cannot diverge.
- **Hosted endpoint** (`scripts/make_space.py`): assembles a Hugging Face Docker Space serving the MCP server over streamable HTTP, so practitioners can connect an AI client to a URL instead of installing Python. Verified locally: the MCP initialize handshake completes over HTTP.
- **`scripts/demo.py`**: runs a realistic scenario (base in São Paulo, fixtures in Fortaleza, Recife and Porto Alegre) through every tool and prints the answers, including the deliberate out-of-scope refusal. No keys, no client, no network.
- Neither addition changes any published value.

## 0.4.1 — 2026-09-18
IQAir's free tier turned out not to be obtainable, so the gap cities needed a different answer.

- **Google Air Quality API added** (`GOOGLE_AIR_QUALITY_KEY`). Fuses stations, satellite and models into µg/m³ at ~500 m and covers all eight venues; Brazil has its own local index alongside the Universal AQI. It needs a billed Google Cloud project — there is no keyless tier — so without a key it returns an error record and the pull carries on with the free sources. It is now the first-choice source for Brasília, Belo Horizonte, Salvador, Recife and Fortaleza.
- **IQAir demoted, not removed.** The Community plan is still advertised but could not be obtained on 18 September 2026. The adapter stays for anyone holding a key, and the registry records why it is not the default.
- **Licence gate on the public archive.** Google and IQAir both restrict redistribution and caching, and the scheduled job commits readings to a public repository twice a day. Sources are now flagged for redistribution: restricted ones are fetched and printed but excluded from the committed archive, with `--archive-all` as an explicit override.
- Values reported in units other than µg/m³ (Google returns some gases in ppb) are dropped rather than mixed into a µg/m³ series.
- 91 automated tests.

## 0.4.0 — 2026-09-18
Every known source is now reachable from the agent — automated where an API exists, named where it does not.

- **New source: IQAir / AirVisual** (`IQAIR_API_KEY`, free tier). Returns true concentrations in µg/m³, not only an index, and has values for Brasília, Recife and Fortaleza, which publish nothing usable to OpenAQ. City-level and partly fused from low-cost sensors, so it is labelled `city_fused` and distance-checked like any station.
- **New tool `list_air_quality_sources`.** For five of the eight host cities the only station data that exists is on a state or municipal portal. The agent now names them — MonitorAr, CETESB QUALAR, the Porto Alegre SMAMUS network, ProAr BH, IBRAM, CPRH, SEMACE, INEMA, the IEMA platform — with what each provides and how to reach it, instead of reporting that no data is available.
- **Source registry** (`sources.REGISTRY`, `sources.BEST_SOURCE`): thirteen sources, four automated, each with coverage, units, cadence, key and URL, plus a per-venue order of preference. `pull_air_quality.py --list-sources` prints it and `--mode probe` names the best source for each venue.
- **The live lookup now chooses properly.** It prefers a current station reading over a model grid cell, and a concentration over an index, and never promotes a reading flagged far, stale or empty — previously it took whichever source answered first. When nothing is available it returns the agency portals to try instead.
- **New script `build_monitorar_climatology.py`**: builds a *measured* June–July climatology for the host cities from MonitorAr's national open data (CC BY), written to `climatology_stations` alongside the modelled CAMS `climatology` so the provenance of each number stays explicit. The download host is not reachable from CI, so the files are fetched by hand once.
- 85 automated tests.

## 0.3.3 — 2026-09-18
Findings and fixes from the first authenticated OpenAQ probe of all eight host cities.

- **Stale station feeds are no longer reported as current air quality.** A station that stops publishing still answers `/latest` with its final measurement. The CETESB stations around São Paulo last reached OpenAQ on 5 April 2023, and those three-year-old readings were being averaged and presented as today's PM2.5 for the largest host city. Readings older than 24 h (configurable) are now excluded, and the record reports which stations were used and which were skipped as stale.
- **Low-cost sensors are distinguished from reference instruments.** Salvador's only station is a community AirGradient unit and Fortaleza's is a HabitatMap test device that has never reported. A venue covered only by low-cost sensors now returns `status: "low_cost_only"` instead of looking equivalent to a government network.
- **Measured station coverage recorded per city** in `air_quality.json` (`station_coverage`), with the probe date: current reference-grade PM2.5 was available for 1 of 8 host cities; WAQI's nearest station was within 50 km for São Paulo only, lying 207–1806 km away for the other seven.
- **Probe output is more useful**: station grade, age of the last reading, and the WAQI station's distance and verdict.
- 76 automated tests; the new regression tests use the actual API responses from the 18 September probe.

## 0.3.2 — 2026-09-18
Fixes found by the first live air-quality pull and the first CI run. No change to any published claim in the article.

- **MCP SDK 2.x support.** The SDK renamed `FastMCP` to `MCPServer` in version 2.0, which broke the server on any fresh install. `server.py` now detects and supports both majors (`MCP_MAJOR`), including the move of the HTTP host/port settings into `run()`. CI tests both `mcp<2` and `mcp>=2` on Python 3.10 and 3.12, so an upstream major release cannot break users silently again.
- **OpenAQ values were silently discarded.** The v3 `/latest` endpoint identifies readings by `sensorsId` with no parameter name, so the previous parameter matching dropped every measurement and all eight cities reported no data while appearing to succeed. Sensor ids are now resolved from the station index.
- **OpenAQ station search widened.** The v3 radius query is capped at 25 km, which returned "no stations" for Brasília, Belo Horizonte, Porto Alegre and Recife. A bounding-box fallback (~50 km) is tried before giving up, and each station's distance from the venue is recorded.
- **WAQI could report another city's air.** The `geo:` lookup returns the nearest station at any distance; Salvador and Recife (677 km apart) received identical readings. Station distance is now measured, and a station beyond 50 km is flagged `far_station` and excluded from planning bands.
- **WAQI units.** WAQI returns US EPA AQI sub-indices, not µg/m³. Treating AQI 65 as 65 µg/m³ overstates PM2.5 roughly fourfold. Readings are now converted with the EPA breakpoints into `values_ugm3_est` and labelled as estimates; raw AQI is retained.
- **Transient failures are retried once** (Brasília failed while the other seven cities succeeded), so a single upstream blip no longer leaves a hole in the archive.
- 71 automated tests; the five regression tests pin each defect above.

## 0.3.1 — 2026-09-18
- Air-quality workflow now runs twice a day (09:10 and 20:10 UTC = 06:10 and 17:10 in Brazil), covering morning training and evening sessions or kick-offs.
- Step-by-step instructions for adding OPENAQ_API_KEY and WAQI_TOKEN as GitHub repository secrets (README, RELEASING.md, docs/air_quality_sources.md), plus a cron alternative.

## 0.3.0 — 2026-09-18
- Air-quality data sources wired in: `wwc27_medagent/sources.py` adapters for Open-Meteo (CAMS, no key), OpenAQ v3 (free key) and WAQI/aqicn (free token), normalised to one record shape with units, provenance and attribution.
- `scripts/pull_air_quality.py` replaces `refresh_air_quality.py` (kept as a shim) and adds `snapshot`, `probe` and `climatology` modes, writing an append-only archive to `data/airq_archive/`.
- `.github/workflows/air-quality.yml` pulls a daily snapshot and commits it; API keys come from repository secrets.
- `get_air_quality(live=True)` now uses the configured sources (`AIRQ_SOURCES`, default Open-Meteo) and reports per-source failures.
- `docs/air_quality_sources.md` compares the automatable sources with the Brazilian reference datasets (IEMA platform, CETESB QUALAR, MonitorAr, BRAIN).
- 66 automated tests (source parsing and failure handling are tested offline with canned payloads).

## 0.2.0 — 2026-09-18
- Air quality added: per-city profiles (typical sources, June–July pattern, monitoring agency), WHO 2021 guideline levels, Brazil's CONAMA 506/2024 staged standards, and author-defined PM2.5 planning bands for training and match decisions.
- New tools: `get_air_quality` (optionally fetching current concentrations from the Open-Meteo/CAMS API when the host machine has internet access) and `plan_respiratory_care` (PM2.5 band plus asthma/EIB screening, management and 2026 anti-doping limits for inhaled beta-2 agonists).
- New resource `wwc27://air-quality`; new Table 2 domain "Airway health, asthma/EIB and air quality"; six new evidence items (E34–E39).
- `scripts/refresh_air_quality.py` fills the June–July climatology from the Open-Meteo archive; not yet run in this release (no network access at build time), so `climatology` is null and the tools say so.
- Benchmark grown from 50 to 61 items (25/13/11/12); 54 automated tests.

## 0.1.0 — 2026-09-17 (manuscript submission draft)
- Initial evidence table (33 claims, 43 references) covering men's World Cups (2014, 2022, 2026), Women's World Cups (2019, 2023), female athlete health consensus statements and Brazil travel health.
- Host-city climate normals (INMET), elevation, and CDC Yellow Book 2026 yellow-fever guidance.
- Tools: venue profile, heat-risk estimate, travel burden, screening checklist, evidence lookup, tournament facts.
- Evidence retrieval uses whole-word matching; generic context words (e.g. "team", "women") do not count on their own; a year named in the question must match the evidence item.
- Validation: 41 automated tests; 50-item benchmark (20 reproduction, 10 application, 10 open-ended, 10 out-of-scope) with tool-layer check, end-to-end evaluation harness and blinded rating workflow.
- Archived on GitHub + Zenodo (see RELEASING.md).
- Known gaps to fill: peer-reviewed surveillance from the 2026 men's World Cup; kick-off times and base camps (after the final draw); 2027 arbovirus bulletins.

## Update triggers (living mode)
- New peer-reviewed tournament surveillance or consensus statement relevant to a domain in Table 2.
- FIFA schedule changes (kick-off times, venues) or heat-policy changes.
- Public-health notices for host states (dengue, Oropouche, yellow fever, measles, respiratory viruses).
- Air-quality updates: the twice-daily workflow keeps the archive current; re-run `pull_air_quality.py --mode climatology` yearly, and check the state monitoring agencies and any WHO/CONAMA changes.
- Annual anti-doping list changes (inhaled beta-2 agonist limits).
- Monthly check from January 2027 and weekly from May 2027 until the final.
