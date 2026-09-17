# WWC27-MedAgent

[![tests](https://github.com/OWNER/wwc27-medagent/actions/workflows/tests.yml/badge.svg)](https://github.com/OWNER/wwc27-medagent/actions/workflows/tests.yml)
<!-- Add the Zenodo DOI badge here after the first release -->

WWC27-MedAgent is a **paper agent** for the Current Opinion *"Sports Medicine and Science Considerations to Maximise Preparation for the FIFA Women's World Cup Brazil 2027: From Static Evidence to a Living Agent"* (Cardinale & Geertsema; submitted to *Sports Medicine*). It follows the Paper2Agent model (Miao et al., *Nature* 2026, doi:10.1038/s41586-026-11044-y). The article's tables, decision tools and evidence base are packaged as a **Model Context Protocol (MCP) server**, so any MCP-compatible AI assistant can answer practitioners' questions from them in plain language, with sources.

> **Decision support only.** Outputs summarise published evidence and climate normals. They do not replace clinical judgement, on-site WBGT measurement or current public-health advice. Do not enter identifiable player data.

## What it exposes

| Type | Name | Purpose |
|---|---|---|
| Tool | `get_venue_profile` | June/July climate normals, elevation, indicative sWBGT and heat band, yellow-fever guidance by host city |
| Tool | `estimate_heat_risk` | Indicative sWBGT from a forecast temperature and humidity; FIFA/FIFPRO reference bands; luteal-phase note |
| Tool | `calculate_travel_burden` | Great-circle legs and climate transitions for an itinerary |
| Tool | `build_screening_checklist` | Phase × domain checklist (Table 2), with venue-specific actions |
| Tool | `find_evidence` | Search of the curated, source-linked evidence table; replies "I don't know" when a question is out of scope |
| Tool | `tournament_facts` | Dates and format |
| Resource | `wwc27://manuscript`, `wwc27://table1-venues`, `wwc27://table2-screening`, `wwc27://evidence`, `wwc27://references`, `wwc27://changelog` | Machine-readable article content |
| Prompt | `pre_tournament_medical_plan`, `venue_briefing` | Step-by-step workflows that call the tools in order |

## Install and test

```bash
git clone https://github.com/OWNER/wwc27-medagent.git && cd wwc27-medagent
pip install -e ".[test]"
pytest -q                          # 41 tests: source values, computations, refusal, MCP registration, benchmark integrity
python benchmark/run_tool_check.py # tool-layer benchmark check
```

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

`benchmark/` contains a 50-item benchmark with four sets:
- 20 reproduction questions;
- 10 application questions;
- 10 open-ended questions, scored by two blinded raters;
- 10 out-of-scope questions.

It also contains the scripts to run the agent against two baselines (the manuscript in the prompt, and closed-book) and to score the results. See [`benchmark/README.md`](benchmark/README.md).

## Archiving and citation

The code is on GitHub, and each release is archived on Zenodo with its own DOI (see [`RELEASING.md`](RELEASING.md)). Cite the article and the specific release you used (`CITATION.cff`). The Zenodo *concept DOI* always resolves to the newest version.

## Living-mode curation

1. A curator adds or edits entries in `wwc27_medagent/data/*.json`. Every claim needs a `ref` that resolves to a DOI or URL in `references.json`.
2. Add a matching assertion to `tests/`, regenerate the benchmark (`python benchmark/build_benchmark.py`) and push. GitHub Actions must pass.
3. Bump the version, add an entry to `wwc27_medagent/data/CHANGELOG.md` and publish a GitHub release. Zenodo then archives it automatically.
4. Update triggers are listed in the changelog: new surveillance data, schedule changes and outbreak notices.

## Data governance

The server holds no personal data. Teams that want outputs for individual players should run it locally inside their own governance environment.

## Licence

Code: MIT. Data tables: CC BY 4.0, with attribution to the article and the original sources.
