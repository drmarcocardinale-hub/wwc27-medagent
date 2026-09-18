"""Generate the public reader site into docs/, served by GitHub Pages.

Why a static site as well as an MCP server: the agent needs an AI client and a Python install,
which most practitioners will not have. The article's tables, evidence base and air-quality data
are already machine-readable, so the same JSON drives a page anyone can open in a browser.

    python scripts/build_site.py          # writes docs/index.html and docs/data/*.json

The page reads the JSON at runtime, so re-running the generator is only needed when the layout
changes; refreshing the data means re-copying the JSON, which this script also does. Everything
is inlined - no CDN, no fonts, no build step - so the page keeps working offline and cannot be
broken by a third party going away.

Enable it once on GitHub: Settings -> Pages -> Source: "Deploy from a branch" -> branch `master`,
folder `/docs`.
"""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "wwc27_medagent" / "data"
DOCS = ROOT / "docs"
FILES = ["venues.json", "screening.json", "evidence.json", "references.json", "air_quality.json"]

REPO = "https://github.com/drmarcocardinale-hub/wwc27-medagent"
CONCEPT_DOI = "10.5281/zenodo.22832165"
# Set this once the Hugging Face Space is live (scripts/make_space.py), then rebuild.
HOSTED_MCP_URL = ""

OPTION1_LIVE = """    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 1 &middot; Hosted endpoint (nothing to install)</h3>
      <p style="font-size:.9rem;margin:0 0 8px">Paste this URL into your assistant's connector
      settings:</p>
      <p><code style="font-family:var(--mono);font-size:.85rem">{url}</code></p>
      <p style="font-size:.85rem;color:var(--muted);margin:8px 0 0">
      In <strong>Claude Desktop</strong>: Settings &rarr; Connectors &rarr; Add custom connector.
      In <strong>Claude Code</strong>:
      <code style="font-family:var(--mono)">claude mcp add --transport http wwc27-medagent {url}</code></p>
      <p style="font-size:.82rem;color:var(--muted);margin:8px 0 0">The free host sleeps after a
      couple of days idle, so the first question after a quiet spell takes a few seconds while it
      wakes.</p>
    </div>"""

OPTION1_PENDING = """    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 1 &middot; Hosted endpoint
        <span class="tag warn">not yet available</span></h3>
      <p style="font-size:.9rem;margin:0">A hosted version, which would need nothing installed, is
      not running yet. Until it is, use Option 2 below. This page will show the address here once
      it is live.</p>
    </div>"""


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WWC27-MedAgent</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%230b6b5e'/%3E%3C/svg%3E">
<meta name="description" content="Sports medicine and science preparation for the FIFA Women's World Cup Brazil 2027: host-city data, screening matrix and source-linked evidence.">
<style>
:root{
  --bg:#fbfaf8; --surface:#fff; --line:#e4e0da; --ink:#1c1a17; --muted:#6b645c;
  --accent:#0b6b5e; --accent-soft:#e6f2f0; --warn:#a8531a; --bad:#9d2f2f;
  --radius:10px; --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#16181a; --surface:#1e2124; --line:#32373c; --ink:#e9e6e1; --muted:#9aa0a6;
  --accent:#5fd3bf; --accent-soft:#16302c; --warn:#e0a061; --bad:#e5847f;
}}
:root[data-theme="dark"]{
  --bg:#16181a; --surface:#1e2124; --line:#32373c; --ink:#e9e6e1; --muted:#9aa0a6;
  --accent:#5fd3bf; --accent-soft:#16302c; --warn:#e0a061; --bad:#e5847f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  line-height:1.55;-webkit-text-size-adjust:100%}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px}
header{border-bottom:1px solid var(--line);background:var(--surface)}
header .wrap{padding-top:28px;padding-bottom:22px}
h1{font-size:clamp(1.4rem,3.4vw,2rem);margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--muted);margin:0 0 14px;font-size:.95rem;max-width:64ch}
.meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:.82rem}
.pill{border:1px solid var(--line);border-radius:999px;padding:3px 10px;color:var(--muted);
  text-decoration:none;background:var(--bg)}
.pill:hover{border-color:var(--accent);color:var(--accent)}
.note{background:var(--accent-soft);border-left:3px solid var(--accent);padding:10px 14px;
  border-radius:0 var(--radius) var(--radius) 0;font-size:.88rem;margin:16px 0}
nav{position:sticky;top:0;z-index:5;background:var(--surface);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;gap:2px;overflow-x:auto;padding-top:0;padding-bottom:0}
nav button{background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);
  font:inherit;font-size:.9rem;padding:12px 12px;cursor:pointer;white-space:nowrap}
nav button[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
main{padding:22px 0 60px}
section[hidden]{display:none}
h2{font-size:1.15rem;margin:0 0 4px}
.lede{color:var(--muted);font-size:.9rem;margin:0 0 16px;max-width:70ch}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:14px 16px;margin-bottom:12px}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.88rem;min-width:560px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;font-size:.76rem;text-transform:uppercase;letter-spacing:.04em;
  color:var(--muted);background:var(--bg);position:sticky;top:0}
tr:last-child td{border-bottom:0}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;font-size:.72rem;padding:2px 7px;border-radius:999px;
  background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.tag.warn{background:#f7ead9;color:var(--warn)}
.tag.bad{background:#f7dedd;color:var(--bad)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .tag.warn{background:#3a2a17}
  :root:not([data-theme="light"]) .tag.bad{background:#3a1f1e}}
input[type=search]{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:var(--radius);
  background:var(--surface);color:var(--ink);font:inherit;font-size:.92rem;margin-bottom:12px}
input[type=search]:focus{outline:2px solid var(--accent);outline-offset:1px}
details{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);
  padding:10px 14px;margin-bottom:8px}
details summary{cursor:pointer;font-weight:600;font-size:.94rem}
details ul{margin:10px 0 4px;padding-left:20px}
details li{margin-bottom:5px;font-size:.89rem}
.phase{color:var(--muted);font-size:.76rem;text-transform:uppercase;letter-spacing:.04em;
  margin:12px 0 2px;font-weight:600}
.ev{border-bottom:1px solid var(--line);padding:12px 0}
.ev:last-child{border-bottom:0}
.ev .id{font-family:var(--mono);font-size:.76rem;color:var(--accent)}
.ev .claim{margin:3px 0 5px}
.ev .src{font-size:.8rem;color:var(--muted)}
a{color:var(--accent)}
ol.refs{padding-left:22px;font-size:.86rem}
ol.refs li{margin-bottom:9px}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.82rem;padding:18px 0 40px}
.empty{color:var(--muted);font-style:italic;padding:16px 0}
</style>
</head>
<body>
<header><div class="wrap">
  <h1>WWC27-MedAgent</h1>
  <p class="sub">Sports medicine and science preparation for the FIFA Women's World Cup Brazil
  2027 &mdash; host-city conditions, a screening and monitoring matrix, and a source-linked
  evidence base. Companion to the Current Opinion by Cardinale &amp; Geertsema.</p>
  <div class="meta">
    <a class="pill" href="__REPO__">Code on GitHub</a>
    <a class="pill" href="https://doi.org/__DOI__">DOI __DOI__</a>
    <a class="pill" href="#use" id="usePill">How to ask it questions</a>
    <span class="pill" id="built">built __BUILT__</span>
  </div>
  <div class="note"><strong>Decision support only.</strong> These pages summarise published
  evidence and climate normals. They do not replace clinical judgement, on-site WBGT measurement
  or current public-health advice.</div>
</div></header>

<nav><div class="wrap" role="tablist">
  <button role="tab" aria-selected="true" data-tab="venues">Host cities</button>
  <button role="tab" aria-selected="false" data-tab="screening">Screening matrix</button>
  <button role="tab" aria-selected="false" data-tab="evidence">Evidence</button>
  <button role="tab" aria-selected="false" data-tab="air">Air quality</button>
  <button role="tab" aria-selected="false" data-tab="refs">References</button>
  <button role="tab" aria-selected="false" data-tab="use">Ask it questions</button>
</div></nav>

<main><div class="wrap">
  <section id="venues">
    <h2>Host cities</h2>
    <p class="lede">June and July climate normals, with an indicative simplified WBGT computed
    from the <strong>mean daily maximum</strong> temperature and the monthly mean humidity &mdash;
    roughly an average afternoon, not the hottest day on record. It ignores sun and wind and does
    not replace on-site measurement. Bands follow FIFA (&gt;32&nbsp;°C mandatory cooling breaks)
    and FIFPRO (28&ndash;32&nbsp;°C).</p>
    <div class="tablewrap"><table id="venueTable"></table></div>
  </section>

  <section id="screening" hidden>
    <h2>Screening and monitoring matrix</h2>
    <p class="lede">Eleven domains across four phases. Open a domain to see the actions for each
    phase and the sources behind them.</p>
    <div id="screeningList"></div>
  </section>

  <section id="evidence" hidden>
    <h2>Evidence base</h2>
    <p class="lede">Every claim the agent will answer from, with its source. Search by topic,
    setting or number.</p>
    <input type="search" id="evSearch" placeholder="Search the evidence (heat, illness, iron, 2023...)" aria-label="Search evidence">
    <div id="evList"></div>
  </section>

  <section id="air" hidden>
    <h2>Air quality</h2>
    <p class="lede">Typical sources and the June&ndash;July pattern per city, with what open
    monitoring data actually exists there.</p>
    <div id="airGuides"></div>
    <div id="airCities"></div>
  </section>

  <section id="use" hidden>
    <h2>Asking it questions</h2>
    <p class="lede">This page is the reference tables. The question-and-answer part runs inside
    your own AI assistant: you connect it to the agent once, then ask in plain language and it
    answers from these same tables, with the source for each claim.</p>

    <div class="note"><strong>There is no chat box on this page, by design.</strong> A static page
    cannot run a language model, and hosting one openly would mean paying per question and
    accepting whatever is typed into it. Connecting your own assistant keeps your questions —
    and any patient or player detail — inside your own environment.</div>

__OPTION1__

    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 2 &middot; Run it on your own machine</h3>
      <p style="font-size:.85rem;color:var(--muted);margin:0 0 8px">Needs Python 3.10 or newer.
      Keeps everything local.</p>
      <pre style="font-family:var(--mono);font-size:.82rem;overflow-x:auto;background:var(--bg);
        padding:10px 12px;border-radius:var(--radius);margin:0"><code>git clone __REPO__.git
cd wwc27-medagent
pip install -e .</code></pre>
      <p style="font-size:.85rem;margin:8px 0 0">Then add to
      <code style="font-family:var(--mono)">claude_desktop_config.json</code>:</p>
      <pre style="font-family:var(--mono);font-size:.82rem;overflow-x:auto;background:var(--bg);
        padding:10px 12px;border-radius:var(--radius);margin:6px 0 0"><code>{ "mcpServers": { "wwc27-medagent": { "command": "wwc27-medagent" } } }</code></pre>
      <p style="font-size:.85rem;margin:8px 0 0">To see what it answers without any AI client at
      all: <code style="font-family:var(--mono)">python scripts/demo.py</code></p>
    </div>

    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 3 &middot; No AI assistant</h3>
      <p style="font-size:.9rem;margin:0">Use the tabs on this page. Everything the agent answers
      from is here: the host-city table, the screening matrix, the evidence base and the
      references. The agent adds convenience and plain-language answers, not extra content.</p>
    </div>

    <h3 style="font-size:1rem;margin:20px 0 6px">Questions it is built to answer</h3>
    <div class="card">
      <p style="margin:0 0 8px;font-size:.9rem"><em>&ldquo;We're based in S&atilde;o Paulo and play
      in Fortaleza, Recife and Porto Alegre. Draft our pre-tournament medical plan.&rdquo;</em></p>
      <p style="margin:0 0 8px;font-size:.9rem"><em>&ldquo;The Salvador forecast is 28&nbsp;&deg;C and
      85% humidity and three starters are likely luteal. What's the heat band and what should we
      do?&rdquo;</em></p>
      <p style="margin:0 0 8px;font-size:.9rem"><em>&ldquo;What did the 2023 Women's World Cup show
      about illness?&rdquo;</em></p>
      <p style="margin:0;font-size:.85rem;color:var(--muted)">Ask it something outside its evidence
      base &mdash; tactics, team selection, an unrelated condition &mdash; and it answers
      &ldquo;I don't know&rdquo; rather than improvising. That refusal is deliberate and is part of
      what the published validation benchmark measures.</p>
    </div>
  </section>

  <section id="refs" hidden>
    <h2>References</h2>
    <p class="lede">Every source cited by the tools above.</p>
    <ol class="refs" id="refList"></ol>
  </section>
</div></main>

<footer><div class="wrap">
  Data: CC BY 4.0. Code: MIT. Cite the article and the archived release
  (<a href="https://doi.org/__DOI__">__DOI__</a>), which always resolves to the current version.
</div></footer>

<script>
const D = {};
const files = ["venues","screening","evidence","references","air_quality","venue_table"];
const esc = s => String(s==null?"":s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// sWBGT and its band are computed by the Python package at build time (see venue_rows).
const bandClass = b => b === "very high" ? "bad" : b === "high" ? "warn" : "";

function renderVenues(){
  const rows = D.venue_table.map(r => `<tr>
      <td><strong>${esc(r.city)}</strong><br><span style="color:var(--muted);font-size:.8rem">${esc(r.stadium)}</span></td>
      <td class="num">${r.elevation_m} m</td>
      <td class="num">${r.june.tmax} / ${r.june.rh}%</td>
      <td class="num">${r.june.swbgt_at_daily_max} <span class="tag ${bandClass(r.june.band)}">${esc(r.june.band)}</span></td>
      <td class="num">${r.july.tmax} / ${r.july.rh}%</td>
      <td class="num">${r.july.swbgt_at_daily_max} <span class="tag ${bandClass(r.july.band)}">${esc(r.july.band)}</span></td>
      <td>${esc(r.yellow_fever)}</td></tr>`).join("");
  document.getElementById("venueTable").innerHTML =
    `<thead><tr><th>City / stadium</th><th>Elev.</th><th>June max °C / RH</th>
     <th>June sWBGT</th><th>July max °C / RH</th><th>July sWBGT</th>
     <th>Yellow fever (CDC 2026)</th></tr></thead><tbody>${rows}</tbody>`;
}

function renderScreening(){
  const doms = D.screening.domains;
  const phases = [["pre_tournament","Pre-tournament"],["preparation_camp","Preparation camp"],
                  ["in_tournament","In tournament"],["post_tournament","Post-tournament"]];
  document.getElementById("screeningList").innerHTML = Object.entries(doms).map(([k,d]) => {
    const body = phases.map(([pk,pl]) => {
      const items = d[pk] || [];
      if (!items.length) return "";
      return `<div class="phase">${pl}</div><ul>${items.map(i=>`<li>${esc(i)}</li>`).join("")}</ul>`;
    }).join("");
    return `<details><summary>${esc(d.label || k)}</summary>${body}</details>`;
  }).join("");
}

function renderEvidence(filter){
  const q = (filter||"").toLowerCase().trim();
  const refs = D.references;
  const items = D.evidence.filter(e => !q ||
    JSON.stringify(e).toLowerCase().includes(q));
  const el = document.getElementById("evList");
  if (!items.length){ el.innerHTML = `<p class="empty">Nothing matches &ldquo;${esc(filter)}&rdquo;.</p>`; return; }
  el.innerHTML = items.map(e => {
    const r = refs[e.ref] || {};
    const link = r.link ? `<a href="${esc(r.link)}">${esc(r.link)}</a>` : "";
    return `<div class="ev">
      <span class="id">${esc(e.id)}</span> <span class="tag">${esc(e.domain||"")}</span>
      ${e.setting?`<span class="tag">${esc(e.setting)}</span>`:""}
      <p class="claim">${esc(e.claim)}</p>
      <p class="src">${esc(r.cite || e.ref || "")} ${link}</p></div>`;
  }).join("");
}

function renderAir(){
  const a = D.air_quality;
  const g = a.guidelines_who_2021_ug_m3 || {};
  const bands = a.planning_bands_pm2_5_24h_ug_m3 || {};
  const gRows = Object.entries(g).filter(([k])=>!k.startsWith("_"))
    .map(([k,v])=>`<tr><td>${esc(k)}</td><td class="num">${esc(typeof v==="object"?JSON.stringify(v):v)}</td></tr>`).join("");
  const bRows = Object.entries(bands).filter(([k])=>!k.startsWith("_"))
    .map(([k,v])=>`<tr><td><span class="tag ${k==="good"?"":(k==="moderate"?"":"warn")}">${esc(k)}</span></td>
      <td class="num">&le; ${esc(v.max ?? "")}</td><td>${esc(v.action||"")}</td></tr>`).join("");
  document.getElementById("airGuides").innerHTML = `
    <div class="card"><strong>WHO 2021 guideline levels (µg/m³)</strong>
      <div class="tablewrap" style="margin-top:8px"><table>${gRows}</table></div></div>
    <div class="card"><strong>Planning bands for PM2.5 over 24 h</strong>
      <p class="lede" style="margin:4px 0 8px">${esc(bands._note||"")}</p>
      <div class="tablewrap"><table><thead><tr><th>Band</th><th>µg/m³</th><th>Action</th></tr></thead>
      <tbody>${bRows}</tbody></table></div></div>`;

  document.getElementById("airCities").innerHTML = Object.entries(a.cities).map(([k,c]) => {
    const cov = c.station_coverage || {};
    const covTag = cov.grade === "reference" ? `<span class="tag">reference stations</span>`
      : cov.grade === "low_cost" ? `<span class="tag warn">low-cost sensor only</span>`
      : cov.grade === "reference_but_stale" ? `<span class="tag warn">indexed but stale</span>`
      : `<span class="tag bad">no open station data</span>`;
    return `<details><summary>${esc((D.venues.venues[k]||{}).city || k)} ${covTag}</summary>
      <p style="font-size:.9rem">${esc(c.typical_sources||"")}</p>
      <p style="font-size:.9rem"><strong>June&ndash;July:</strong> ${esc(c.june_july_note||"")}</p>
      <p style="font-size:.85rem;color:var(--muted)"><strong>Agency:</strong>
        ${esc((c.monitoring||{}).agency||"")}${cov.note?" &middot; "+esc(cov.note):""}</p>
      </details>`;
  }).join("");
}

function renderRefs(){
  document.getElementById("refList").innerHTML = Object.entries(D.references)
    .map(([k,r]) => `<li id="ref-${esc(k)}">${esc(r.cite||"")}
      ${r.link?` <a href="${esc(r.link)}">${esc(r.link)}</a>`:""}</li>`).join("");
}

document.querySelectorAll("nav button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("nav button").forEach(x => x.setAttribute("aria-selected", String(x===b)));
  document.querySelectorAll("main section").forEach(s => s.hidden = (s.id !== b.dataset.tab));
  try { localStorage.setItem("wwc27-tab", b.dataset.tab); } catch (e) {}
}));

document.getElementById("evSearch").addEventListener("input", e => renderEvidence(e.target.value));

document.getElementById("usePill").addEventListener("click", e => {
  e.preventDefault();
  document.querySelector('nav button[data-tab="use"]').click();
  window.scrollTo({top: 0, behavior: "smooth"});
});

Promise.all(files.map(f => fetch(`data/${f}.json`).then(r => r.json()).then(j => D[f] = j)))
  .then(() => {
    renderVenues(); renderScreening(); renderEvidence(""); renderAir(); renderRefs();
    try {
      const t = localStorage.getItem("wwc27-tab");
      if (t) document.querySelector(`nav button[data-tab="${t}"]`)?.click();
    } catch (e) {}
  })
  .catch(err => {
    document.querySelector("main .wrap").innerHTML =
      `<p class="empty">Could not load the data files (${esc(err.message)}). ` +
      `If you are viewing this page from your own disk, serve it with ` +
      `<code>python3 -m http.server</code> instead of opening the file directly.</p>`;
  });
</script>
</body>
</html>
"""


def venue_rows() -> list[dict]:
    """Pre-compute the venue table with the package's own functions.

    The page must not re-implement simplified WBGT in JavaScript: two implementations of a
    clinical calculation drift apart, and the published number should be the one the agent and
    the manuscript use. So the values are computed here, by core, and the page only renders them.
    """
    import sys
    sys.path.insert(0, str(ROOT))
    from wwc27_medagent import core

    rows = []
    for key, v in core.venues().items():
        row = {"key": key, "city": v["city"], "stadium": v["stadium"],
               "elevation_m": v["elevation_m"],
               "yellow_fever": v.get("yellow_fever_vaccine_cdc_2026", "")}
        for m in ("june", "july"):
            mm = v[m]
            at_max = core.simplified_wbgt(mm["tmax"], mm["rh"])
            row[m] = {"tmax": mm["tmax"], "rh": mm["rh"],
                      "swbgt_at_daily_max": round(at_max, 1),
                      "band": core.heat_band(at_max)["band"]}
        rows.append(row)
    return rows


def main() -> int:
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(DATA / f, DOCS / "data" / f)
        json.loads((DOCS / "data" / f).read_text(encoding="utf-8"))   # fail loudly on bad JSON
    (DOCS / "data" / "venue_table.json").write_text(
        json.dumps(venue_rows(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    option1 = OPTION1_LIVE.format(url=HOSTED_MCP_URL) if HOSTED_MCP_URL else OPTION1_PENDING
    html = (HTML.replace("__OPTION1__", option1)
                .replace("__REPO__", REPO)
                .replace("__DOI__", CONCEPT_DOI)
                .replace("__BUILT__", date.today().isoformat()))
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    kb = (DOCS / "index.html").stat().st_size / 1024
    print(f"docs/index.html ({kb:.0f} kB) + {len(FILES)} data files")
    print("Enable once: GitHub -> Settings -> Pages -> Deploy from a branch -> master -> /docs")
    print(f"Then it serves at https://drmarcocardinale-hub.github.io/wwc27-medagent/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
