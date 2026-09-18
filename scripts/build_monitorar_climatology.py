"""Build a MEASURED June-July air-quality climatology for the host cities from MonitorAr.

Why this exists
---------------
The climatology currently in `air_quality.json` comes from CAMS model grid cells (~40 km),
because live station coverage for the host cities is poor: a probe on 2026-09-18 found current
reference-grade PM2.5 in open station data for one of eight cities. MonitorAr, the Brazilian
national air-quality system (Ministry of the Environment), publishes the official station
measurements as annual open-data files under CC BY. Those are real instruments, and June-July
2022-2025 is exactly the tournament window.

The files are not downloadable from an automated environment (the download host is not on the
egress allowlist), so this is a manual, one-off step:

  1. Open https://dados.mma.gov.br/dataset/ar-puro-monitorar
  2. Download the yearly archives you want, e.g.
     dados_monitorar_2022.zip ... dados_monitorar_2025.zip
  3. Put them in one folder, then:

       python scripts/build_monitorar_climatology.py --inspect data/monitorar   # show the schema
       python scripts/build_monitorar_climatology.py data/monitorar             # build

`--inspect` prints the columns and a sample of rows without writing anything. Run it first: the
published schema may change between years, and the column mapping below is a best guess that
`--inspect` lets you confirm or correct via --col-* options.

Output goes to `air_quality.json` under "climatology_stations", alongside (not replacing) the
modelled "climatology", so the two can be compared and the provenance of each stays explicit.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics as st
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from wwc27_medagent import core

AQ_FILE = Path(core.__file__).parent / "data" / "air_quality.json"

# Column names vary between years and are accented; these are substrings matched case- and
# accent-insensitively. Override any of them with --col-<name> if --inspect shows something else.
GUESS = {
    "city":      ["municipio", "cidade", "nm_municipio"],
    "state":     ["uf", "sigla_uf", "estado"],
    "station":   ["estacao", "nome_estacao", "nm_estacao", "local"],
    "pollutant": ["poluente", "parametro", "nm_poluente"],
    "value":     ["valor", "concentracao", "medida", "vl_medida"],
    "unit":      ["unidade", "un_medida"],
    "datetime":  ["data_hora", "datahora", "data", "dt_medicao", "data_medicao"],
    "lat":       ["latitude", "lat"],
    "lon":       ["longitude", "lon", "lng"],
}
PM25_TOKENS = ("pm2,5", "pm2.5", "pm25", "mp2,5", "mp2.5", "mp25", "material particulado fino")


def _fold(s: str) -> str:
    """lower-case, strip accents and non-alphanumerics, so 'Município' == 'municipio'."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _pick(header: list[str], candidates: list[str]) -> str | None:
    folded = {_fold(h): h for h in header}
    for cand in candidates:                      # exact fold match first
        if cand in folded:
            return folded[cand]
    for cand in candidates:                      # then substring
        for f, original in folded.items():
            if cand in f:
                return original
    return None


def _rows(path: Path):
    """Yield (filename, header, row-dict) from every CSV inside a zip, or a bare CSV."""
    def read_csv(name: str, data: bytes):
        for enc in ("utf-8-sig", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        for row in reader:
            yield name, reader.fieldnames or [], row

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.filename.lower().endswith(".csv") and not info.is_dir():
                    yield from read_csv(info.filename, z.read(info))
    elif path.suffix.lower() == ".csv":
        yield from read_csv(path.name, path.read_bytes())


def _files(folder: Path) -> list[Path]:
    fs = sorted([p for p in folder.iterdir() if p.suffix.lower() in (".zip", ".csv")])
    if not fs:
        raise SystemExit(f"No .zip or .csv files in {folder}. Download them from "
                         "https://dados.mma.gov.br/dataset/ar-puro-monitorar first.")
    return fs


def _num(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace(".", "").replace(",", ".") if str(v).count(",") == 1 else str(v).strip()
    try:
        x = float(s)
    except ValueError:
        return None
    return None if x < 0 else x          # negatives are instrument flags, not concentrations


def _month(v) -> int | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    if m:
        return int(m.group(2))
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(v))
    return int(m.group(2)) if m else None


def _year(v) -> int | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v)) or re.search(r"(\d{2})/(\d{2})/(\d{4})", str(v))
    if not m:
        return None
    return int(m.group(1)) if "-" in str(v)[:10] else int(m.group(3))


def do_inspect(folder: Path, limit: int = 3) -> int:
    for f in _files(folder):
        print(f"\n=== {f.name}")
        seen = 0
        for name, header, row in _rows(f):
            if seen == 0:
                print(f"  file: {name}")
                print(f"  columns ({len(header)}): {header}")
                mapping = {k: _pick(header, v) for k, v in GUESS.items()}
                print("  auto-mapped:")
                for k, v in mapping.items():
                    print(f"    {k:<10} -> {v}")
                missing = [k for k, v in mapping.items() if v is None and k in
                           ("city", "pollutant", "value", "datetime")]
                if missing:
                    print(f"  !! could not map: {missing}. Pass --col-{missing[0]} <column name>.")
            print(f"  row {seen + 1}: { {k: row[k] for k in list(row)[:8]} }")
            seen += 1
            if seen >= limit:
                break
    print("\nIf the mapping looks right, run without --inspect to build the climatology.")
    return 0


def do_build(folder: Path, overrides: dict[str, str | None], months: tuple[int, ...]) -> int:
    venues = core.venues()
    # Match on city name, accent-insensitively; keep the state to disambiguate.
    by_city = {_fold(v["city"]): k for k, v in venues.items()}
    by_city.setdefault("brasilia", "brasilia")

    pooled: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    stations: dict[str, set[str]] = defaultdict(set)
    years: dict[str, set[int]] = defaultdict(set)
    scanned = kept = 0

    for f in _files(folder):
        mapping: dict[str, str | None] = {}
        for name, header, row in _rows(f):
            if not mapping:
                mapping = {k: overrides.get(k) or _pick(header, v) for k, v in GUESS.items()}
                need = [k for k in ("city", "pollutant", "value", "datetime") if not mapping.get(k)]
                if need:
                    print(f"  {f.name}: cannot map {need}; skipping. Run --inspect.")
                    break
            scanned += 1
            city_key = by_city.get(_fold(row.get(mapping["city"])))
            if not city_key:
                continue
            if _fold(row.get(mapping["pollutant"])) not in {_fold(t) for t in PM25_TOKENS}:
                continue
            when = row.get(mapping["datetime"])
            if _month(when) not in months:
                continue
            val = _num(row.get(mapping["value"]))
            if val is None:
                continue
            pooled[city_key]["pm2_5"].append(val)
            kept += 1
            if mapping.get("station"):
                stations[city_key].add(str(row.get(mapping["station"])))
            y = _year(when)
            if y:
                years[city_key].add(y)
        print(f"  {f.name}: scanned {scanned:,} rows, kept {kept:,} PM2.5 readings so far")

    if not pooled:
        print("\nNo PM2.5 rows matched the host cities. Run --inspect and check the column "
              "mapping and the pollutant spelling in this year's files.")
        return 1

    payload = json.loads(AQ_FILE.read_text(encoding="utf-8"))
    out = {}
    for city_key, series in pooled.items():
        vals = sorted(series["pm2_5"])
        if len(vals) < 24:
            print(f"  {city_key}: only {len(vals)} readings - too few, skipped")
            continue
        out[city_key] = {
            "pm2_5": {"mean": round(st.mean(vals), 1),
                      "median": round(st.median(vals), 1),
                      "p95": round(vals[int(0.95 * (len(vals) - 1))], 1),
                      "max": round(vals[-1], 1),
                      "n": len(vals)},
            "years": sorted(years[city_key]),
            "n_stations": len(stations[city_key]) or None,
            "stations": sorted(stations[city_key])[:12] or None,
            "period": "1 June - 31 July",
            "units": "ug/m3",
            "source": "MonitorAr (Sistema Nacional de Gestao da Qualidade do Ar), "
                      "Ministerio do Meio Ambiente e Mudanca do Clima, CC BY. "
                      "https://dados.mma.gov.br/dataset/ar-puro-monitorar",
            "measurement": "reference station network (not modelled)"}
        s = out[city_key]["pm2_5"]
        print(f"{city_key:<18} PM2.5 mean {s['mean']:>5} ug/m3  median {s['median']:>5}  "
              f"p95 {s['p95']:>6}  n={s['n']:,}  years {sorted(years[city_key])}")

    payload["climatology_stations"] = out
    payload["_meta"]["climatology_stations_status"] = (
        f"Built {date.today().isoformat()} from MonitorAr annual open data (CC BY) for "
        f"1 June - 31 July. Measured reference-station values for {len(out)} of 8 host cities; "
        "the modelled CAMS climatology is kept separately for the cities without stations.")
    AQ_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote measured climatology for {len(out)} cities -> {AQ_FILE.name}. "
          "Run pytest, add a CHANGELOG entry, and cite MonitorAr in the article.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="folder holding the downloaded MonitorAr zip/csv files")
    ap.add_argument("--inspect", action="store_true", help="print the schema and exit")
    ap.add_argument("--months", default="6,7", help="months to pool (default 6,7)")
    for k in GUESS:
        ap.add_argument(f"--col-{k}", dest=f"col_{k}", default=None,
                        help=f"column name holding {k}")
    a = ap.parse_args()
    if not a.folder.is_dir():
        raise SystemExit(f"{a.folder} is not a folder")
    if a.inspect:
        return do_inspect(a.folder)
    overrides = {k: getattr(a, f"col_{k}") for k in GUESS}
    months = tuple(int(m) for m in a.months.split(","))
    return do_build(a.folder, overrides, months)


if __name__ == "__main__":
    raise SystemExit(main())
