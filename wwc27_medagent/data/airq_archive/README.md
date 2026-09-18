# Air-quality archive

Written by `scripts/pull_air_quality.py`:

- `YYYY-MM.jsonl` — one JSON record per venue per source per pull (append-only).
- `latest.json` — the most recent pull, for quick inspection and for the agent.

Records are normalised: `{source, venue, city, observed_at, kind, units, values{pm2_5,pm10,no2,o3}, detail, attribution}`.
Failed pulls are stored too (`status: "error"`), so gaps in the series are visible.

Units differ by source: Open-Meteo and OpenAQ report µg/m³; WAQI reports AQI sub-indices. Do not mix them in one series.
