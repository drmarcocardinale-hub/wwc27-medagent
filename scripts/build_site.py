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
# Set once the Cloud Run service is live (deploy/cloudrun/), then rebuild the site.
HOSTED_MCP_URL = "https://wwc27-medagent-919325462297.europe-west1.run.app/mcp"
# The same service serves a browser chat at its root. Derived rather than written out twice, so
# moving the service cannot leave the page advertising two different hosts.
HOSTED_CHAT_URL = HOSTED_MCP_URL[:-4] if HOSTED_MCP_URL.endswith("/mcp") else ""

# Brazil's border from Natural Earth 1:50m (naturalearthdata.com), which is public domain and
# asks for no attribution; the figure credits it anyway. Simplified with Douglas-Peucker to a
# ~1 px tolerance at the size the map is drawn, and projected to Mercator once here so the page
# can place the venues from venues.json through the same transform.
BRAZIL = {
    "path": "M181.8 103.1 195.3 114.8 212.3 109.2 217.6 116.7 227.0 106.1 249.9 95.3 255.0 85.0 269.7 79.3 270.8 72.8 254.0 70.5 249.5 42.7 235.1 25.1 254.6 34.0 272.0 33.6 284.3 42.6 288.0 31.7 331.6 18.5 341.2 9.4 340.6 0.9 353.6 0.5 357.5 4.5 353.4 18.6 364.8 22.5 368.7 33.9 360.9 42.7 357.4 65.7 365.7 89.8 386.2 103.6 395.2 101.6 399.6 93.8 407.4 95.5 430.7 82.9 460.2 86.9 455.8 76.7 460.4 70.0 466.1 72.9 485.3 68.0 507.0 80.2 516.2 74.2 536.7 78.6 575.1 24.2 581.2 29.8 594.1 79.9 600.6 87.6 613.4 92.0 614.9 104.7 593.1 128.7 579.6 136.5 561.8 169.2 544.4 173.9 562.7 174.8 589.5 158.3 594.7 179.3 602.1 185.8 629.9 178.5 621.6 202.1 632.5 183.2 645.3 172.3 651.6 175.5 654.5 172.1 651.9 163.6 660.4 153.1 682.0 150.8 728.2 168.9 731.5 178.2 738.0 171.7 748.8 178.9 751.7 186.7 746.1 192.1 748.5 194.9 754.3 189.7 755.7 194.7 747.0 216.1 759.6 197.4 762.7 198.0 760.5 206.0 781.2 195.0 829.7 208.8 868.4 207.4 906.4 229.2 939.6 259.8 981.0 265.4 989.0 276.6 1000.0 320.8 995.9 349.6 979.8 378.9 934.9 427.2 934.8 423.3 926.4 445.4 912.4 464.8 905.8 467.7 900.9 459.0 896.8 463.4 899.0 466.4 890.7 484.3 896.0 544.3 887.8 579.3 889.1 593.4 876.4 608.1 873.0 643.7 843.1 689.0 842.0 709.9 824.0 718.5 816.9 725.9 815.4 736.1 792.0 736.6 787.0 729.9 785.2 737.3 768.0 740.4 773.7 737.8 768.8 735.1 749.2 739.1 750.9 745.1 728.1 759.9 715.1 759.7 692.3 772.0 663.7 794.4 665.2 798.1 658.2 805.1 653.1 801.1 651.2 805.9 644.7 803.8 653.1 810.3 646.4 817.3 644.3 829.3 649.2 855.8 643.0 895.6 618.8 918.6 588.8 974.6 560.3 1000.3 559.7 991.7 569.5 990.0 579.9 981.1 582.7 970.4 594.8 958.1 594.1 949.9 597.5 950.2 598.0 944.8 586.2 948.2 579.2 938.3 582.8 948.0 579.6 959.5 573.9 970.0 562.0 978.3 556.4 993.4 558.1 1001.9 544.7 1031.3 526.4 1049.7 522.3 1047.1 522.3 1032.3 532.6 1019.1 520.5 1009.0 516.4 998.5 480.4 975.2 469.4 962.5 459.2 969.3 458.1 960.3 438.0 940.4 428.3 945.6 418.2 942.8 462.1 889.6 467.3 890.0 466.3 884.8 489.1 866.0 514.4 853.6 518.7 828.1 510.0 809.7 494.6 809.7 504.1 766.7 494.3 760.1 474.2 764.0 464.4 719.7 447.9 712.0 435.4 717.4 408.6 711.2 412.6 682.5 404.2 659.7 411.8 654.7 404.9 648.3 421.1 607.1 412.5 588.2 398.1 580.8 399.4 555.5 352.7 555.1 351.0 534.1 342.3 524.1 350.3 523.8 344.3 489.6 329.7 481.7 311.6 482.7 303.2 473.1 286.7 468.8 279.0 460.2 244.4 454.2 229.9 442.1 219.7 423.1 219.6 383.3 189.5 388.2 137.2 419.5 121.8 415.6 85.7 417.0 88.3 376.2 70.5 389.9 46.4 390.9 41.4 378.1 20.2 375.5 26.2 364.7 0.0 327.7 7.2 321.3 6.2 310.9 22.1 299.6 19.6 290.2 28.4 265.2 55.0 249.4 81.7 240.9 102.8 244.2 117.4 164.8 111.4 147.3 100.3 137.9 100.7 119.6 123.7 117.5 119.7 107.5 105.9 107.3 106.0 90.7 148.6 90.4 148.2 83.6 154.8 89.7 168.4 80.3 175.6 90.9 176.5 104.1 181.8 103.1ZM621.8 140.2 653.4 141.9 642.1 169.8 633.5 170.4 631.9 175.1 624.9 172.9 617.3 180.0 599.4 180.0 593.0 166.0 597.6 162.5 592.0 157.5 595.9 141.3 606.0 137.3 621.8 140.2Z",
    "lon0": -74.0021,
    "lat0": -33.7422,
    "lat1": 5.258,
    "sx": 1461.7545,
    "y_top": 0.091898,
    "width": 1000.0,
    "height": 1049.7
}

CHAT_CARD = """    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 1 &middot; Ask it in your browser
        <span class="tag">nothing to install</span></h3>
      <p style="font-size:.9rem;margin:0 0 10px">Type a question and the agent answers from the
      same tables this page shows, naming the tool it used and linking the source. No account, no
      client to configure, eight questions a day.</p>
      <p style="margin:0 0 10px"><a href="{chat}" style="font-weight:600">Open the chat &rarr;</a></p>
      <p style="font-size:.82rem;color:var(--muted);margin:0">Every answer is produced by calling
      the same tools as Option 2, so the two cannot disagree. Questions are sent to the hosted
      service and on to a commercial model API; nothing is written to disk there, but
      <strong>do not type patient or player detail into it</strong>. Where that matters, use
      Option 2 or 3 and keep the whole exchange inside your own environment.</p>
    </div>"""

OPTION1_LIVE = """    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 2 &middot; Connect your own assistant</h3>
      <p style="font-size:.9rem;margin:0 0 8px">Paste this URL into your assistant's connector
      settings:</p>
      <p><code style="font-family:var(--mono);font-size:.85rem">{url}</code></p>
      <p style="font-size:.85rem;color:var(--muted);margin:8px 0 0">
      In <strong>Claude Desktop</strong>: Settings &rarr; Connectors &rarr; Add custom connector.
      In <strong>Claude Code</strong>:
      <code style="font-family:var(--mono)">claude mcp add --transport http wwc27-medagent {url}</code></p>
      <p style="font-size:.82rem;color:var(--muted);margin:8px 0 0">The service scales to zero
      when unused, so the first question after an idle spell waits a few seconds for a cold start.
      Later questions answer immediately.</p>
    </div>"""

OPTION1_PENDING = """    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 2 &middot; Connect your own assistant
        <span class="tag warn">not yet available</span></h3>
      <p style="font-size:.9rem;margin:0">A hosted version, which would need nothing installed, is
      not running yet. Until it is, use Option 3 below. This page will show the address here once
      it is live.</p>
    </div>"""


OTHER_CLIENTS = """    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Using an assistant other than Claude</h3>
      <p style="font-size:.9rem;margin:0 0 8px">The agent speaks the Model Context Protocol, which
      is not tied to any one vendor. Any assistant, IDE extension or agent framework that supports
      MCP over HTTP can use it. In its settings look for <em>MCP</em>, <em>remote MCP server</em> or
      <em>custom connector</em>, and give it the transport and the URL:</p>
      <p style="font-size:.85rem;margin:0 0 8px">Transport: <strong>streamable HTTP</strong> &middot;
      URL: <code style="font-family:var(--mono);font-size:.82rem">__URL__</code></p>
      <p style="font-size:.85rem;margin:8px 0 6px">Most clients that use a config file take this
      shape:</p>
      <pre style="font-family:var(--mono);font-size:.82rem;overflow-x:auto;background:var(--bg);
        padding:10px 12px;border-radius:var(--radius);margin:0"><code>{ "mcpServers": { "wwc27-medagent": {
    "type": "streamable-http",
    "url": "__URL__"
} } }</code></pre>
      <p style="font-size:.85rem;margin:10px 0 0">If your client only supports local servers, install
      it as in Option 3 and point the client at the <code style="font-family:var(--mono)">command</code>
      form instead &mdash; that works with any MCP client, not only Claude.</p>
    </div>

    <div class="card">
      <h3 style="margin:0 0 8px;font-size:1rem">ChatGPT and GitHub Copilot</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px">
        <div>
          <p style="font-size:.86rem;margin:0 0 6px"><strong>ChatGPT</strong> &mdash; Settings
          &rarr; Connectors &rarr; Advanced &rarr; turn on <em>Developer mode</em>. Then
          Connectors &rarr; Create, paste the URL above and choose <em>No authentication</em>.
          In a chat, open the + menu, pick Developer mode and tick the connector.</p>
          <p style="font-size:.8rem;color:var(--muted);margin:0">Plus, Pro, Business, Enterprise
          and Edu on the web; not Free. On Business and Enterprise an administrator enables
          Developer mode first.</p>
        </div>
        <div>
          <p style="font-size:.86rem;margin:0 0 6px"><strong>GitHub Copilot</strong> &mdash; in
          VS Code, add the server to <code style="font-family:var(--mono)">.vscode/mcp.json</code>
          and use agent mode:</p>
          <pre style="font-family:var(--mono);font-size:.78rem;background:var(--bg);
            white-space:pre-wrap;word-break:break-all;
            padding:9px 11px;border-radius:var(--radius);margin:0"><code>{ "servers": { "wwc27-medagent": {
    "type": "http",
    "url": "__URL__"
} } }</code></pre>
          <p style="font-size:.8rem;color:var(--muted);margin:8px 0 0">Or run
          <code style="font-family:var(--mono)">code --add-mcp</code>.</p>
        </div>
      </div>
      <p style="font-size:.8rem;color:var(--muted);margin:12px 0 0">Menu paths checked
      13&nbsp;Oct&nbsp;2026 and they do move. If one has changed, look for <em>MCP</em>,
      <em>connector</em> or <em>remote server</em> in the settings and give it the transport and
      URL above &mdash; those do not change.</p>
    </div>

    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">No MCP support? Call it over plain HTTP</h3>
      <p style="font-size:.9rem;margin:0 0 8px">The endpoint is JSON-RPC, so any language model
      wrapper, script or agent framework that can make an HTTP request can use the tools directly.
      The server is stateless, so no handshake is needed &mdash; list the tools, then call one:</p>
      <pre style="font-family:var(--mono);font-size:.8rem;overflow-x:auto;background:var(--bg);
        padding:10px 12px;border-radius:var(--radius);margin:0"><code>curl -sS -X POST __URL__ \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

curl -sS -X POST __URL__ \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{
        "name":"estimate_heat_risk",
        "arguments":{"temperature_c":28,"relative_humidity_pct":85,"luteal_phase":true}}}'</code></pre>
      <p style="font-size:.85rem;color:var(--muted);margin:10px 0 0">Replies come back as a
      Server-Sent Events frame: the JSON is on the <code style="font-family:var(--mono)">data:</code>
      line. Feed the tool descriptions from <code style="font-family:var(--mono)">tools/list</code> to
      your own model as its tool schema, and it can call these the same way Claude does.</p>
    </div>
"""


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
  --bg:#faf9f7; --surface:#fff; --surface-2:#f5f3ef; --line:#e4e0da; --line-soft:#efece6;
  --ink:#1c1a17; --ink-2:#47423b; --muted:#6b645c;
  --accent:#0b6b5e; --accent-soft:#e6f2f0;
  --low:#2a78d6; --low-soft:#e7effc;
  --ok:#0e8a72; --ok-soft:#e3f1ed;
  --warn:#cf7a12; --warn-soft:#fbeeda;
  --bad:#9d2f2f; --bad-soft:#f8e4e3;
  --grid:#eae6e0; --axis:#cfc9c0;
  --s1:#b9f5e3; --s2:#a3e5d2; --s3:#8cd4c0; --s4:#75c4ae;
  --s5:#5ab29b; --s6:#3ca088; --s7:#1d8c75; --s8:#0b7661;
  --radius:12px; --radius-sm:8px;
  --shadow:0 1px 2px rgba(28,26,23,.05), 0 8px 24px -16px rgba(28,26,23,.18);
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
/* Dark is selected, not flipped: its own ramp steps and band colours, each validated against
   the dark surface. Declared under both scopes so an explicit theme wins over the OS setting. */
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#141619; --surface:#1e2124; --surface-2:#252a2e; --line:#32373c; --line-soft:#282d31;
  --ink:#e9e6e1; --ink-2:#c2bdb6; --muted:#9aa0a6;
  --accent:#5fd3bf; --accent-soft:#16302c;
  --low:#3987e5; --low-soft:#172539;
  --ok:#22a893; --ok-soft:#14302b;
  --warn:#c08a1a; --warn-soft:#332714;
  --bad:#c94a4a; --bad-soft:#331e1e;
  --grid:#2a2f33; --axis:#3d4449;
  --s1:#083f36; --s2:#144d43; --s3:#1e5d51; --s4:#296c60;
  --s5:#347c6f; --s6:#3f8c7d; --s7:#529c8d; --s8:#66aa9c;
  --shadow:0 1px 2px rgba(0,0,0,.30), 0 8px 24px -16px rgba(0,0,0,.60);
}}
:root[data-theme="dark"]{
  --bg:#141619; --surface:#1e2124; --surface-2:#252a2e; --line:#32373c; --line-soft:#282d31;
  --ink:#e9e6e1; --ink-2:#c2bdb6; --muted:#9aa0a6;
  --accent:#5fd3bf; --accent-soft:#16302c;
  --low:#3987e5; --low-soft:#172539;
  --ok:#22a893; --ok-soft:#14302b;
  --warn:#c08a1a; --warn-soft:#332714;
  --bad:#c94a4a; --bad-soft:#331e1e;
  --grid:#2a2f33; --axis:#3d4449;
  --s1:#083f36; --s2:#144d43; --s3:#1e5d51; --s4:#296c60;
  --s5:#347c6f; --s6:#3f8c7d; --s7:#529c8d; --s8:#66aa9c;
  --shadow:0 1px 2px rgba(0,0,0,.30), 0 8px 24px -16px rgba(0,0,0,.60);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  line-height:1.55;-webkit-text-size-adjust:100%;font-synthesis-weight:none}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}

header{border-bottom:1px solid var(--line);background:
  radial-gradient(120% 140% at 12% -10%, var(--accent-soft) 0%, transparent 58%), var(--surface)}
header .wrap{padding-top:36px;padding-bottom:26px}
.eyebrow{font-size:.72rem;letter-spacing:.11em;text-transform:uppercase;color:var(--accent);
  font-weight:700;margin:0 0 10px}
h1{font-size:clamp(1.55rem,3.6vw,2.3rem);margin:0 0 8px;letter-spacing:-.022em;line-height:1.15}
.sub{color:var(--ink-2);margin:0 0 18px;font-size:1rem;max-width:62ch}
.meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:.82rem}
.pill{border:1px solid var(--line);border-radius:999px;padding:4px 11px;color:var(--muted);
  text-decoration:none;background:var(--surface);transition:border-color .15s,color .15s}
.pill:hover{border-color:var(--accent);color:var(--accent)}

/* Four single numbers that are not a chart: a bar chart of one value per bar would say less. */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:var(--radius);
  overflow:hidden;margin:22px 0 4px}
.stat{background:var(--surface);padding:12px 14px}
.stat b{display:block;font-size:1.5rem;line-height:1.1;letter-spacing:-.02em;font-weight:650;white-space:nowrap}
.stat>span{display:block;font-size:.76rem;color:var(--muted);margin-top:3px}
.stat b span{display:inline;font-size:.92rem;font-weight:500;color:var(--muted)}

.note{background:var(--accent-soft);border-left:3px solid var(--accent);padding:11px 15px;
  border-radius:0 var(--radius-sm) var(--radius-sm) 0;font-size:.88rem;margin:18px 0}
nav{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--surface) 88%,transparent);
  backdrop-filter:saturate(1.6) blur(8px);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;gap:2px;overflow-x:auto;padding-top:0;padding-bottom:0}
nav button{background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);
  font:inherit;font-size:.9rem;padding:13px 13px;cursor:pointer;white-space:nowrap}
nav button:hover{color:var(--ink)}
nav button[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent);font-weight:650}
main{padding:26px 0 72px}
section[hidden]{display:none}
h2{font-size:1.3rem;margin:0 0 5px;letter-spacing:-.015em}
.lede{color:var(--muted);font-size:.9rem;margin:0 0 18px;max-width:72ch}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 18px;margin-bottom:14px;box-shadow:var(--shadow)}

/* Figures: one chart per figure, its legend above the plot and its caption below. */
figure.viz{margin:0 0 18px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px 18px 12px;box-shadow:var(--shadow)}
figure.viz h3{margin:0 0 2px;font-size:.98rem;letter-spacing:-.01em}
figure.viz .vsub{margin:0 0 12px;font-size:.82rem;color:var(--muted);max-width:70ch}
figure.viz figcaption{margin-top:10px;font-size:.78rem;color:var(--muted);max-width:76ch}
.vizbody{position:relative;overflow-x:auto}
.vizbody svg{display:block;width:100%;height:auto;overflow:visible;min-width:var(--vmin,0)}
.legend{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:0 0 12px;font-size:.78rem;
  color:var(--ink-2)}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;
  vertical-align:-1px}
.legend .swatch{display:flex;align-items:center}
.scale{display:flex;align-items:center;gap:7px;font-size:.74rem;color:var(--muted)}
.scale .bar{display:flex;height:9px;border-radius:3px;overflow:hidden;width:132px}
.scale .bar span{flex:1}
.vtip{position:absolute;pointer-events:none;opacity:0;transition:opacity .09s;z-index:3;
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);
  padding:7px 10px;font-size:.78rem;box-shadow:var(--shadow);min-width:118px;line-height:1.4}
.vtip strong{font-size:.88rem}
.vtip .k{color:var(--muted)}
.vizgrid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:14px;
  align-items:start}
@media (max-width:860px){.vizgrid{grid-template-columns:1fr}}

.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);
  background:var(--surface);box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;font-size:.88rem;min-width:560px}
th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--line-soft);vertical-align:top}
th{font-weight:650;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);background:var(--surface-2);position:sticky;top:0}
tr:last-child td{border-bottom:0}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}

/* Screening overview: a shaded table is its own table view, and every cell prints its count,
   so the shading is a second read of the number rather than the only way to get it. */
table.matrix{min-width:520px;font-size:.84rem}
table.matrix td.cell{text-align:center;font-variant-numeric:tabular-nums;cursor:pointer;
  padding:0;border-bottom:1px solid var(--surface)}
table.matrix td.cell>span{display:block;padding:9px 6px;margin:1px;border-radius:5px;
  color:var(--ink)}
table.matrix td.cell:hover>span{outline:2px solid var(--accent);outline-offset:-2px}
table.matrix th.dom{font-weight:500;text-transform:none;letter-spacing:0;font-size:.84rem;
  color:var(--ink);background:var(--surface);position:static;white-space:normal;min-width:190px}

.tryrow{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin-bottom:12px}
.tryrow label{display:flex;flex-direction:column;font-size:.76rem;color:var(--muted);gap:4px}
.tryrow input[type=number],.tryrow select{font:inherit;padding:7px 9px;border:1px solid var(--line);
  border-radius:var(--radius-sm);background:var(--surface);color:var(--ink);min-width:130px}
.tryrow label.chk{flex-direction:row;align-items:center;gap:6px;color:var(--ink);font-size:.9rem}
.tryrow button{font:inherit;padding:8px 13px;border:1px solid var(--line);
  border-radius:var(--radius-sm);background:var(--accent-soft);color:var(--accent);cursor:pointer;
  font-weight:600}
.tryrow button:hover{border-color:var(--accent)}
.tryout{border-top:1px solid var(--line);padding-top:14px;margin-top:6px}
.bignum{font-size:2rem;line-height:1.05;letter-spacing:-.025em;font-weight:650}

.tag{display:inline-block;font-size:.71rem;font-weight:600;padding:2px 8px;border-radius:999px;
  background:var(--ok-soft);color:var(--ok);white-space:nowrap}
.tag.low{background:var(--low-soft);color:var(--low)}
.tag.warn{background:var(--warn-soft);color:var(--warn)}
.tag.bad{background:var(--bad-soft);color:var(--bad)}
input[type=search]{width:100%;padding:11px 13px;border:1px solid var(--line);
  border-radius:var(--radius);background:var(--surface);color:var(--ink);font:inherit;
  font-size:.92rem;margin-bottom:14px}
details{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);
  padding:11px 15px;margin-bottom:8px}
details[open]{box-shadow:var(--shadow)}
details summary{cursor:pointer;font-weight:650;font-size:.94rem}
details ul{margin:10px 0 4px;padding-left:20px}
details li{margin-bottom:5px;font-size:.89rem}
.phase{color:var(--accent);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;
  margin:14px 0 2px;font-weight:700}
.ev{border-bottom:1px solid var(--line-soft);padding:13px 0}
.ev:last-child{border-bottom:0}
.ev .id{font-family:var(--mono);font-size:.74rem;color:var(--accent)}
.ev .claim{margin:4px 0 5px}
.ev .src{font-size:.8rem;color:var(--muted)}
a{color:var(--accent)}
ol.refs{padding-left:22px;font-size:.86rem}
ol.refs li{margin-bottom:9px}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.82rem;padding:22px 0 48px}
.empty{color:var(--muted);font-style:italic;padding:16px 0}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<header><div class="wrap">
  <p class="eyebrow">Living companion to a Current Opinion</p>
  <h1>WWC27-MedAgent</h1>
  <p class="sub">Sports medicine and science preparation for the FIFA Women's World Cup Brazil
  2027 &mdash; host-city conditions, a screening and monitoring matrix, and a source-linked
  evidence base. Companion to the Current Opinion by Cardinale &amp; Geertsema.</p>
  <div class="stats">
    <div class="stat"><b>8</b><span>host cities</span></div>
    <div class="stat"><b>64</b><span>matches, 24 Jun &ndash; 25 Jul 2027</span></div>
    <div class="stat"><b>3200<span> km</span></b><span>Porto Alegre to Fortaleza</span></div>
    <div class="stat"><b>17&ndash;35<span> &deg;C</span></b><span>indicative sWBGT range</span></div>
  </div>
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
  <button role="tab" aria-selected="false" data-tab="tryit">Try it</button>
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
    <div class="vizgrid">
      <figure class="viz">
        <h3>Indicative heat load, venue by venue</h3>
        <p class="vsub">Simplified WBGT at each city's mean daily maximum. The dot is July, the
        ring is June; the gap between them is how much the month matters.</p>
        <div class="legend" id="bandLegend"></div>
        <div class="vizbody" style="--vmin:520px"><div id="venueChart"></div><div class="vtip" id="venueTip"></div></div>
        <figcaption>Shaded zones: FIFPRO advises cooling breaks from 28&nbsp;&deg;C; FIFA's
        historical policy made them mandatory above 32&nbsp;&deg;C. Values are an average
        afternoon, not the hottest day on record, and ignore sun and wind.</figcaption>
      </figure>
      <figure class="viz">
        <h3>Where the eight venues sit</h3>
        <p class="vsub">Coloured by the same July band. Fortaleza is 3&deg; south of the equator;
        Porto Alegre is below the tropic, in winter.</p>
        <div class="vizbody" style="--vmin:300px"><div id="venueMap"></div><div class="vtip" id="mapTip"></div></div>
        <figcaption>Outline: Natural Earth 1:50m, public domain. Mercator projection.</figcaption>
      </figure>
    </div>
    <div class="tablewrap"><table id="venueTable"></table></div>
  </section>

  <section id="screening" hidden>
    <h2>Screening and monitoring matrix</h2>
    <p class="lede">Eleven domains across four phases. Open a domain to see the actions for each
    phase and the sources behind them.</p>
    <figure class="viz">
      <h3>Where the actions sit</h3>
      <p class="vsub">Number of checklist items in each domain and phase; a stronger colour
      means more to do. Select a cell to open that domain.</p>
      <div class="scale" style="margin-bottom:10px"><span>fewer</span>
        <span class="bar" id="matrixScale"></span><span>more</span></div>
      <div class="tablewrap" style="box-shadow:none"><table class="matrix" id="matrixTable"></table></div>
      <figcaption>The counts are the items listed below, not a measure of effort or importance.</figcaption>
    </figure>
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
    <p class="lede">This page is the reference tables. To ask questions of them in plain language,
    and get the source for each claim, take whichever route below suits you &mdash; they are
    ordered by how much you have to set up, which is nothing at all for the first.</p>

    <div class="note"><strong>Why the chat is not on this page itself.</strong> This page is
    static, served from a file; it cannot run a language model. The chat is a separate hosted
    service, which is also why it can be rationed and why its privacy terms differ: what you type
    there leaves your machine, whereas Options 2 and 3 keep the exchange inside your own
    environment. For anything touching an identifiable player, use those.</div>

__CHATCARD__

__OPTION1__

__OTHERCLIENTS__

    <div class="card">
      <h3 style="margin:0 0 6px;font-size:1rem">Option 3 &middot; Run it on your own machine</h3>
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
      <h3 style="margin:0 0 6px;font-size:1rem">Option 4 &middot; No AI assistant</h3>
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

  <section id="tryit" hidden>
    <h2>Try it</h2>
    <p class="lede">The heat calculation the agent performs, run here in the page. Enter a
    forecast, or prefill one from a host city's July normals. Every number below was produced by
    the Python package at build time rather than re-implemented in JavaScript, so this panel and
    the agent cannot give different answers. Indicative only: it ignores sun and wind and does not
    replace on-site WBGT measurement.</p>

    <div class="card">
      <div class="tryrow">
        <label>Temperature &deg;C<input type="number" id="tT" value="28" min="15" max="45" step="0.5"></label>
        <label>Relative humidity %<input type="number" id="tH" value="85" min="20" max="100" step="5"></label>
        <label class="chk"><input type="checkbox" id="tL"> Luteal phase</label>
      </div>
      <div class="tryrow">
        <label>Prefill from host city<select id="tCity"></select></label>
        <button type="button" id="tFill">Use July daily max</button>
      </div>
      <p id="tFillNote" style="font-size:.8rem;color:var(--muted);margin:-4px 0 10px"></p>
      <div id="tOut" class="tryout"></div>
    </div>

    <figure class="viz">
      <h3>The whole surface, not just one answer</h3>
      <p class="vsub">Every combination the agent holds: 15&ndash;45&nbsp;&deg;C against
      20&ndash;100% humidity. The cross marks your input; the two lines are the 28 and
      32&nbsp;&deg;C band thresholds.</p>
      <div class="scale" id="heatScale"></div>
      <div class="vizbody" style="--vmin:470px"><div id="heatMap"></div><div class="vtip" id="heatTip"></div></div>
      <figcaption>1,037 cells, each computed by the Python package at build time. Hover or focus
      a cell for its value.</figcaption>
    </figure>

    <p style="font-size:.85rem;color:var(--muted);margin-top:14px">This panel covers one tool.
    For the rest &mdash; screening checklists, travel burden, the evidence base, air quality &mdash;
    connect an assistant to the agent: see <a href="#use" id="tryUseLink">how to ask it questions</a>.</p>
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
const files = ["venues","screening","evidence","references","air_quality","venue_table","heat_grid"];
const esc = s => String(s==null?"":s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// sWBGT and its band are computed by the Python package at build time (see venue_rows).
const bandClass = b => ({"very high":"bad","high":"warn","low":"low"})[b] || "";
const BANDS = ["low","moderate","high","very high"];
const BAND_FILL = {"low":"var(--low)","moderate":"var(--ok)","high":"var(--warn)","very high":"var(--bad)"};
const BAND_SOFT = {"low":"var(--low-soft)","moderate":"var(--ok-soft)","high":"var(--warn-soft)","very high":"var(--bad-soft)"};
const OUTLINE = __OUTLINE__;
const rad = d => d * Math.PI / 180;

// Tooltips enhance; they never gate a value. Every number here is also in a table on the page.
function tipOn(tip, host, x, y, html){
  tip.innerHTML = html;
  tip.style.opacity = "1";
  const hw = host.clientWidth, t = tip.getBoundingClientRect();
  let left = x + 16, top = y - t.height - 12;
  if (left + t.width > hw) left = x - t.width - 16;
  if (top < 0) top = y + 18;
  tip.style.left = Math.max(0, left) + "px";
  tip.style.top = Math.max(0, top) + "px";
}
const tipOff = tip => { tip.style.opacity = "0"; };


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
    return `<details id="dom-${esc(k)}"><summary>${esc(d.label || k)}</summary>${body}</details>`;
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
  // These were printing raw JSON ({"annual":5,"24h":15}) and a dangling "<=" on the open-ended
  // top band. Same numbers, read as a table rather than as a dump.
  const PERIOD = {annual:"annual mean", "24h":"24-hour", "8h":"8-hour", peak_season:"peak season"};
  const POLL = {pm2_5:"PM2.5", pm10:"PM10", no2:"NO\u2082", o3:"Ozone"};
  const human = k => k.replace(/_/g, " ");
  const gRows = Object.entries(g).filter(([k]) => !k.startsWith("_") && k !== "source")
    .map(([k,v]) => {
      const parts = (v && typeof v === "object")
        ? Object.entries(v).map(([pk,pv]) => `${pv} <span style="color:var(--muted)">${esc(PERIOD[pk]||pk)}</span>`).join(" &middot; ")
        : esc(v);
      return `<tr><td>${esc(POLL[k]||human(k))}</td><td class="num">${parts}</td></tr>`;
    }).join("");
  const BAND_TAG = {good:"", moderate:"", elevated:"warn", high:"warn", very_high:"bad"};
  const bRows = Object.entries(bands).filter(([k])=>!k.startsWith("_"))
    .map(([k,v]) => {
      const range = v.max == null ? "above 50" : "&le; " + v.max;
      return `<tr><td><span class="tag ${BAND_TAG[k] ?? ""}">${esc(human(k))}</span></td>
      <td class="num">${range}</td><td>${esc(v.action||"")}</td></tr>`;
    }).join("");
  document.getElementById("airGuides").innerHTML = `
    <div class="card"><strong>WHO 2021 guideline levels (µg/m³)</strong>
      <div class="tablewrap" style="margin-top:8px;box-shadow:none"><table>
      <thead><tr><th>Pollutant</th><th>Guideline level</th></tr></thead><tbody>${gRows}</tbody></table></div></div>
    <div class="card"><strong>Planning bands for PM2.5 over 24 h</strong>
      <p class="lede" style="margin:4px 0 8px">${esc(bands._note||"")}</p>
      <div class="tablewrap" style="box-shadow:none"><table><thead><tr><th>Band</th><th style="text-transform:none">µg/m³</th><th>Action</th></tr></thead>
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

function heatLookup(t, h){
  const G = D.heat_grid, T = G.temp_c, H = G.rh_pct;
  const clamp = (v,a,b) => Math.min(b, Math.max(a, v));
  // Snap to the pre-computed grid, then show the snapped inputs, so what the reader sees is
  // exactly what produced the number - no hidden rounding between input and answer.
  const st = clamp(Math.round(t / T.step) * T.step, T.min, T.max);
  const sh = clamp(Math.round(h / H.step) * H.step, H.min, H.max);
  const i = Math.round((st - T.min) / T.step), j = Math.round((sh - H.min) / H.step);
  const band = G.bands[G.band_index[i][j]];
  return {t: st, h: sh, swbgt: G.swbgt[i][j], band: band, action: G.actions[band]};
}

function renderTryIt(){
  const G = D.heat_grid;
  const t = parseFloat(document.getElementById("tT").value);
  const h = parseFloat(document.getElementById("tH").value);
  const out = document.getElementById("tOut");
  if (!isFinite(t) || !isFinite(h)) { out.innerHTML = `<p class="empty">Enter a temperature and a humidity.</p>`; return; }
  const r = heatLookup(t, h);
  const note = (document.getElementById("tL").checked && G.luteal_note)
    ? `<p style="font-size:.85rem;margin:10px 0 0"><strong>Luteal phase.</strong> ${esc(G.luteal_note.note)}
       <a href="${esc(G.luteal_note.source.link)}">${esc(G.luteal_note.source.key)}</a></p>` : "";
  out.innerHTML = `
    <p style="margin:0 0 6px;font-size:.8rem;color:var(--muted)">Computed for ${r.t}&nbsp;&deg;C and ${r.h}% relative humidity</p>
    <p style="margin:0" class="bignum">${r.swbgt}&nbsp;&deg;C <span style="font-size:.95rem;font-weight:400;color:var(--muted)">sWBGT</span>
      <span class="tag ${bandClass(r.band)}">${esc(r.band)}</span></p>
    <p style="font-size:.9rem;margin:8px 0 0">${esc(r.action)}</p>
    ${note}
    <p style="font-size:.8rem;color:var(--muted);margin:10px 0 0">${esc(G.thresholds)}
      &middot; <a href="${esc(G.source.link)}">${esc(G.source.key)}</a></p>`;
  updateHeatCross();
}

function initTryIt(){
  const sel = document.getElementById("tCity");
  sel.innerHTML = D.venue_table.map((r,i) => `<option value="${i}">${esc(r.city)}</option>`).join("");
  const note = document.getElementById("tFillNote");
  document.getElementById("tFill").addEventListener("click", () => {
    const r = D.venue_table[sel.value];
    document.getElementById("tT").value = r.july.tmax;
    document.getElementById("tH").value = r.july.rh;
    renderTryIt();
    // The grid cannot land on arbitrary normals, so say plainly what was rounded and point at
    // the exact figure rather than leaving two slightly different numbers on the same site.
    const snapped = heatLookup(r.july.tmax, r.july.rh);
    note.innerHTML = (snapped.t !== r.july.tmax || snapped.h !== r.july.rh)
      ? `${esc(r.city)}'s July normals are ${r.july.tmax}&nbsp;&deg;C and ${r.july.rh}%, rounded here to
         the nearest grid point. The Host cities tab computes them unrounded, at
         <strong>${r.july.swbgt_at_daily_max}&nbsp;&deg;C</strong>.`
      : "";
  });
  ["tT","tH","tL"].forEach(id =>
    document.getElementById(id).addEventListener("input", () => { note.innerHTML = ""; renderTryIt(); }));
  document.getElementById("tryUseLink").addEventListener("click", e => {
    e.preventDefault();
    document.querySelector('nav button[data-tab="use"]').click();
    window.scrollTo({top: 0, behavior: "smooth"});
  });
  renderTryIt();
}

function renderBandLegend(){
  document.getElementById("bandLegend").innerHTML =
    BANDS.map(b => `<span class="swatch"><i style="background:${BAND_FILL[b]}"></i>${esc(b)}</span>`).join("")
    + `<span class="swatch" style="color:var(--muted)">
         <svg width="26" height="12" style="margin-right:4px" aria-hidden="true"><circle cx="6" cy="6" r="4.5"
         fill="var(--surface)" stroke="var(--ink-2)" stroke-width="2"/></svg>June</span>`
    + `<span class="swatch" style="color:var(--muted)">
         <svg width="26" height="12" style="margin-right:4px" aria-hidden="true"><circle cx="6" cy="6" r="5.5"
         fill="var(--ink-2)"/></svg>July</span>`;
}

function renderVenueChart(){
  const rows = D.venue_table.slice()
    .sort((a,b) => b.july.swbgt_at_daily_max - a.july.swbgt_at_daily_max);
  const W = 800, L = 150, R = 104, rowH = 31, top = 38;
  const H = top + rows.length * rowH + 14;
  const lo = 20, hi = 36;                       // covers 22.4 to 34.9 with air at both ends
  const X = v => L + (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (W - L - R);
  const yOf = i => top + i * rowH + rowH / 2;

  let g = "";
  // Threshold zones first, so every mark sits on top of them.
  g += `<rect x="${X(28)}" y="${top - 12}" width="${X(32) - X(28)}" height="${H - top - 2}" fill="var(--warn-soft)"/>`;
  g += `<rect x="${X(32)}" y="${top - 12}" width="${X(hi) - X(32)}" height="${H - top - 2}" fill="var(--bad-soft)"/>`;
  [28, 32].forEach(v => {
    g += `<line x1="${X(v)}" y1="${top - 12}" x2="${X(v)}" y2="${H - 14}" stroke="var(--axis)" stroke-width="1"/>`;
  });
  g += `<text x="${X(28) + 5}" y="${top - 18}" font-size="10.5" fill="var(--warn)">28 FIFPRO</text>`;
  g += `<text x="${X(32) + 5}" y="${top - 18}" font-size="10.5" fill="var(--bad)">32 FIFA</text>`;
  // x axis
  for (let v = 20; v <= 36; v += 4){
    g += `<text x="${X(v)}" y="${H - 2}" font-size="10.5" fill="var(--muted)" text-anchor="middle">${v}</text>`;
  }
  g += `<line x1="${L}" y1="${H - 14}" x2="${W - R}" y2="${H - 14}" stroke="var(--axis)" stroke-width="1"/>`;
  g += `<text x="${L - 14}" y="${H - 2}" font-size="10.5" fill="var(--muted)" text-anchor="end">&deg;C sWBGT</text>`;

  rows.forEach((r, i) => {
    const y = yOf(i), jn = r.june.swbgt_at_daily_max, jl = r.july.swbgt_at_daily_max;
    const fill = BAND_FILL[r.july.band] || "var(--ok)";
    g += `<text x="${L - 14}" y="${y + 4}" font-size="12.5" fill="var(--ink)" text-anchor="end">${esc(r.city)}</text>`;
    g += `<line x1="${X(jn)}" y1="${y}" x2="${X(jl)}" y2="${y}" stroke="var(--axis)" stroke-width="2" stroke-linecap="round"/>`;
    g += `<circle cx="${X(jn)}" cy="${y}" r="4.5" fill="var(--surface)" stroke="${fill}" stroke-width="2"/>`;
    g += `<circle cx="${X(jl)}" cy="${y}" r="6.5" fill="${fill}" stroke="var(--surface)" stroke-width="2"/>`;
    g += `<text x="${W - R + 10}" y="${y + 4}" font-size="12" fill="var(--ink)" style="font-variant-numeric:tabular-nums">${jl.toFixed(1)}</text>`;
    g += `<text x="${W - R + 44}" y="${y + 4}" font-size="10.5" fill="${fill}">${esc(r.july.band)}</text>`;
    g += `<rect class="hit" data-i="${i}" x="0" y="${y - rowH / 2}" width="${W}" height="${rowH}" fill="transparent"/>`;
  });

  const host = document.getElementById("venueChart");
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Indicative sWBGT by host city, June and July">${g}</svg>`;
  const tip = document.getElementById("venueTip"), body = host.parentElement;
  host.querySelectorAll("rect.hit").forEach(el => {
    const r = rows[+el.dataset.i];
    const show = ev => {
      const b = body.getBoundingClientRect();
      tipOn(tip, body, ev.clientX - b.left, ev.clientY - b.top,
        `<strong>${esc(r.city)}</strong><br><span class="k">${esc(r.stadium)}</span><br>
         June ${r.june.swbgt_at_daily_max} &deg;C &middot; ${esc(r.june.band)}<br>
         July ${r.july.swbgt_at_daily_max} &deg;C &middot; ${esc(r.july.band)}<br>
         <span class="k">${r.elevation_m} m &middot; ${r.july.tmax} &deg;C / ${r.july.rh}% in July</span>`);
    };
    el.addEventListener("mousemove", show);
    el.addEventListener("mouseleave", () => tipOff(tip));
  });
}

function renderVenueMap(){
  const O = OUTLINE;
  const mx = lon => (rad(lon) - rad(O.lon0)) * O.sx;
  const my = lat => (O.y_top - Math.log(Math.tan(rad(45 + lat / 2)))) * O.sx;
  const W = O.width, H = O.height;
  let g = `<path d="${O.path}" fill="var(--surface-2)" stroke="var(--axis)" stroke-width="3" stroke-linejoin="round"/>`;

  [[0, "Equator"], [-23.4367, "Tropic of Capricorn"]].forEach(([lat, label]) => {
    const y = my(lat);
    if (y < 6 || y > H - 6) return;
    g += `<line x1="0" y1="${y.toFixed(1)}" x2="${W}" y2="${y.toFixed(1)}" stroke="var(--grid)" stroke-width="3"/>`;
    g += `<text x="8" y="${(y - 10).toFixed(1)}" font-size="23" fill="var(--muted)">${label}</text>`;
  });

  const pts = D.venue_table.map(r => {
    const v = (D.venues.venues || {})[r.key] || {};
    return {r: r, x: mx(v.lon), y: my(v.lat)};
  }).filter(q => isFinite(q.x) && isFinite(q.y));

  const fz = pts.find(q => q.r.key === "fortaleza"), pa = pts.find(q => q.r.key === "porto_alegre");
  if (fz && pa){
    g += `<line x1="${fz.x.toFixed(1)}" y1="${fz.y.toFixed(1)}" x2="${pa.x.toFixed(1)}" y2="${pa.y.toFixed(1)}" stroke="var(--axis)" stroke-width="2.5"/>`;
    // a quarter of the way down the line is open interior; the midpoint is on top of Brasilia
    const lx = fz.x + (pa.x - fz.x) * 0.27, ly = fz.y + (pa.y - fz.y) * 0.27;
    g += `<text x="${(lx - 14).toFixed(1)}" y="${(ly - 10).toFixed(1)}" font-size="24" fill="var(--ink-2)" text-anchor="end" paint-order="stroke" stroke="var(--surface)" stroke-width="7">3200 km</text>`;
  }

  // Place each label on the side with room, then push overlapping ones apart down the column.
  const GAP = 36;
  [["r", q => q.x <= 640], ["l", q => q.x > 640]].forEach(([side, test]) => {
    const col = pts.filter(test).sort((a, b) => a.y - b.y);
    let last = -1e9;
    col.forEach(q => {
      q.ly = Math.max(q.y, last + GAP);
      last = q.ly;
      q.side = side;
    });
  });

  pts.forEach(q => {
    const fill = BAND_FILL[q.r.july.band] || "var(--ok)";
    const lx = q.side === "l" ? q.x - 26 : q.x + 26;
    if (Math.abs(q.ly - q.y) > 2){
      g += `<line x1="${q.x.toFixed(1)}" y1="${q.y.toFixed(1)}" x2="${lx.toFixed(1)}" y2="${(q.ly - 7).toFixed(1)}" stroke="var(--axis)" stroke-width="2"/>`;
    }
    g += `<circle cx="${q.x.toFixed(1)}" cy="${q.y.toFixed(1)}" r="15" fill="${fill}" stroke="var(--surface)" stroke-width="5"/>`;
    g += `<text x="${lx.toFixed(1)}" y="${(q.ly + 8).toFixed(1)}" font-size="26" fill="var(--ink)"
       text-anchor="${q.side === "l" ? "end" : "start"}" paint-order="stroke" stroke="var(--surface)" stroke-width="7">${esc(q.r.city)}</text>`;
    g += `<circle class="hit" data-k="${esc(q.r.key)}" cx="${q.x.toFixed(1)}" cy="${q.y.toFixed(1)}" r="44" fill="transparent"/>`;
  });

  const host = document.getElementById("venueMap");
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H.toFixed(1)}" role="img" aria-label="Map of Brazil with the eight host cities">${g}</svg>`;
  const tip = document.getElementById("mapTip"), body = host.parentElement;
  host.querySelectorAll("circle.hit").forEach(el => {
    const q = pts.find(z => z.r.key === el.dataset.k);
    el.addEventListener("mousemove", ev => {
      const b = body.getBoundingClientRect();
      tipOn(tip, body, ev.clientX - b.left, ev.clientY - b.top,
        `<strong>${esc(q.r.city)}</strong><br><span class="k">${esc(q.r.stadium)}</span><br>
         July ${q.r.july.swbgt_at_daily_max} &deg;C sWBGT &middot; ${esc(q.r.july.band)}<br>
         <span class="k">Yellow fever: ${esc(q.r.yellow_fever)}</span>`);
    });
    el.addEventListener("mouseleave", () => tipOff(tip));
  });
}

// One hue, light to dark: magnitude is a sequential job, and a rainbow would invent categories.
const HEAT_LO = 16, HEAT_HI = 42;
const heatStep = v => Math.max(1, Math.min(8, Math.floor((v - HEAT_LO) / (HEAT_HI - HEAT_LO) * 8) + 1));

function renderHeatScale(){
  document.getElementById("heatScale").innerHTML =
    `<span>${HEAT_LO}</span><span class="bar">` +
    [1,2,3,4,5,6,7,8].map(i => `<span style="background:var(--s${i})"></span>`).join("") +
    `</span><span>${HEAT_HI}+ &deg;C sWBGT</span>`;
}

function renderHeatMap(){
  const G = D.heat_grid, T = G.temp_c, Hp = G.rh_pct;
  const nT = G.swbgt.length, nH = G.swbgt[0].length;
  const W = 600, H = 384, mL = 46, mR = 12, mT = 10, mB = 34;
  const cw = (W - mL - mR) / nH, ch = (H - mT - mB) / nT;
  const px = j => mL + j * cw;
  const py = i => mT + (nT - 1 - i) * ch;            // hot at the top
  const pyT = t => mT + (nT - 1 - (t - T.min) / T.step) * ch;

  let g = "";
  for (let i = 0; i < nT; i++){
    for (let j = 0; j < nH; j++){
      g += `<rect x="${px(j).toFixed(1)}" y="${py(i).toFixed(1)}" width="${(cw + 0.5).toFixed(1)}" height="${(ch + 0.5).toFixed(1)}" fill="var(--s${heatStep(G.swbgt[i][j])})"/>`;
    }
  }
  // Band thresholds as contours, so the bands are readable without relying on the ramp.
  [[28, "var(--warn)"], [32, "var(--bad)"]].forEach(([thr, col]) => {
    const pts = [];
    for (let j = 0; j < nH; j++){
      for (let i = 1; i < nT; i++){
        const a = G.swbgt[i - 1][j], b = G.swbgt[i][j];
        if ((a < thr && b >= thr)){
          const f = (thr - a) / (b - a);
          pts.push([px(j) + cw / 2, pyT(T.min + (i - 1 + f) * T.step)]);
          break;
        }
      }
    }
    if (pts.length < 2) return;
    g += `<polyline points="${pts.map(q => q[0].toFixed(1) + "," + q[1].toFixed(1)).join(" ")}" fill="none" stroke="${col}" stroke-width="2.5"/>`;
    const first = pts[0];
    g += `<text x="${(first[0] + 7).toFixed(1)}" y="${(first[1] - 8).toFixed(1)}" font-size="11" fill="${col}" paint-order="stroke" stroke="var(--surface)" stroke-width="4">${thr} &deg;C</text>`;
  });
  // axes
  for (let v = Hp.min; v <= Hp.max; v += 20){
    const x = px((v - Hp.min) / Hp.step) + cw / 2;
    g += `<text x="${x.toFixed(1)}" y="${H - 14}" font-size="10.5" fill="var(--muted)" text-anchor="middle">${v}</text>`;
  }
  g += `<text x="${((W - mR + mL) / 2).toFixed(1)}" y="${H - 1}" font-size="10.5" fill="var(--muted)" text-anchor="middle">relative humidity %</text>`;
  for (let v = 15; v <= 45; v += 5){
    g += `<text x="${mL - 8}" y="${(pyT(v) + 4).toFixed(1)}" font-size="10.5" fill="var(--muted)" text-anchor="end">${v}</text>`;
  }
  g += `<text transform="translate(11,${(mT + (H - mT - mB) / 2).toFixed(1)}) rotate(-90)" font-size="10.5" fill="var(--muted)" text-anchor="middle">air temperature &deg;C</text>`;
  g += `<g id="heatCross"></g><rect id="heatHit" x="${mL}" y="${mT}" width="${W - mL - mR}" height="${H - mT - mB}" fill="transparent"/>`;

  const host = document.getElementById("heatMap");
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Simplified WBGT for every combination of air temperature and relative humidity">${g}</svg>`;

  const tip = document.getElementById("heatTip"), body = host.parentElement;
  const hit = host.querySelector("#heatHit");
  hit.addEventListener("mousemove", ev => {
    const svg = host.querySelector("svg"), b = svg.getBoundingClientRect();
    const sx = W / b.width;
    const j = Math.max(0, Math.min(nH - 1, Math.floor(((ev.clientX - b.left) * sx - mL) / cw)));
    const i = Math.max(0, Math.min(nT - 1, nT - 1 - Math.floor(((ev.clientY - b.top) * sx - mT) / ch)));
    const bb = body.getBoundingClientRect();
    tipOn(tip, body, ev.clientX - bb.left, ev.clientY - bb.top,
      `<strong>${G.swbgt[i][j]} &deg;C</strong> sWBGT<br>
       <span class="k">${(T.min + i * T.step).toFixed(1)} &deg;C air &middot; ${Hp.min + j * Hp.step}% RH</span><br>
       ${esc(G.bands[G.band_index[i][j]])}`);
  });
  hit.addEventListener("mouseleave", () => tipOff(tip));
  updateHeatCross();
}

function updateHeatCross(){
  const el = document.getElementById("heatCross");
  if (!el || !D.heat_grid) return;
  const G = D.heat_grid, T = G.temp_c, Hp = G.rh_pct;
  const nT = G.swbgt.length, nH = G.swbgt[0].length;
  const W = 600, H = 384, mL = 46, mR = 12, mT = 10, mB = 34;
  const cw = (W - mL - mR) / nH, ch = (H - mT - mB) / nT;
  const t = parseFloat(document.getElementById("tT").value);
  const h = parseFloat(document.getElementById("tH").value);
  if (!isFinite(t) || !isFinite(h)){ el.innerHTML = ""; return; }
  const r = heatLookup(t, h);
  const j = Math.round((r.h - Hp.min) / Hp.step), i = Math.round((r.t - T.min) / T.step);
  const x = mL + j * cw, y = mT + (nT - 1 - i) * ch;
  el.innerHTML =
    `<rect x="${(x - 1).toFixed(1)}" y="${(y - 1).toFixed(1)}" width="${(cw + 2).toFixed(1)}" height="${(ch + 2).toFixed(1)}" fill="none" stroke="var(--surface)" stroke-width="4"/>` +
    `<rect x="${(x - 1).toFixed(1)}" y="${(y - 1).toFixed(1)}" width="${(cw + 2).toFixed(1)}" height="${(ch + 2).toFixed(1)}" fill="none" stroke="var(--ink)" stroke-width="2"/>` +
    `<text x="${(x + cw + 8).toFixed(1)}" y="${(y + 4).toFixed(1)}" font-size="11.5" fill="var(--ink)" paint-order="stroke" stroke="var(--surface)" stroke-width="4">${r.swbgt} &deg;C</text>`;
}

function renderMatrix(){
  const doms = D.screening.domains;
  const phases = [["pre_tournament","Pre-tournament"],["preparation_camp","Prep camp"],
                  ["in_tournament","In tournament"],["post_tournament","Post-tournament"]];
  const keys = Object.keys(doms);
  let max = 1;
  keys.forEach(k => phases.forEach(([pk]) => { max = Math.max(max, (doms[k][pk] || []).length); }));
  document.getElementById("matrixScale").innerHTML =
    [2,3,4,5,6,7,8].map(i => `<span style="background:var(--s${i})"></span>`).join("");
  const head = `<thead><tr><th class="dom">Domain</th>${phases.map(([,l]) => `<th>${l}</th>`).join("")}</tr></thead>`;
  const body = keys.map(k => {
    const cells = phases.map(([pk]) => {
      const n = (doms[k][pk] || []).length;
      const step = n === 0 ? 0 : Math.max(2, Math.min(8, Math.round(2 + (n / max) * 6)));
      const bg = n === 0 ? "var(--surface)" : `var(--s${step})`;
      const ink = (!n) ? "var(--muted)" : (step >= 6 ? "var(--surface)" : "var(--ink)");
      return `<td class="cell" data-k="${esc(k)}" title="${n} item${n === 1 ? "" : "s"}">
        <span style="background:${bg};color:${ink}">${n || "&middot;"}</span></td>`;
    }).join("");
    return `<tr><th class="dom" scope="row">${esc(doms[k].label || k)}</th>${cells}</tr>`;
  }).join("");
  const el = document.getElementById("matrixTable");
  el.innerHTML = head + `<tbody>${body}</tbody>`;
  el.querySelectorAll("td.cell").forEach(td => td.addEventListener("click", () => {
    const d = document.getElementById("dom-" + td.dataset.k);
    if (!d) return;
    d.open = true;
    d.scrollIntoView({behavior: "smooth", block: "center"});
  }));
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
    renderBandLegend(); renderVenueChart(); renderVenueMap(); renderMatrix();
    renderHeatScale(); renderHeatMap(); initTryIt();
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


HEAT_T_MIN, HEAT_T_MAX, HEAT_T_STEP = 15.0, 45.0, 0.5
HEAT_RH_MIN, HEAT_RH_MAX, HEAT_RH_STEP = 20, 100, 5


def heat_grid() -> dict:
    """Pre-compute sWBGT and its band across a grid of conditions with the package's own
    functions, so the Try it panel can look values up instead of re-implementing the formula in
    JavaScript. Same reasoning as venue_rows: the page and the agent must not be able to disagree.
    tests/test_site.py checks every cell against core."""
    from wwc27_medagent import core          # local import, as venue_rows does

    temps, rhs = [], []
    v = HEAT_T_MIN
    while v <= HEAT_T_MAX + 1e-9:
        temps.append(round(v, 1)); v += HEAT_T_STEP
    v = HEAT_RH_MIN
    while v <= HEAT_RH_MAX + 1e-9:
        rhs.append(v); v += HEAT_RH_STEP

    bands = ["low", "moderate", "high", "very high"]
    swbgt, index = [], []
    for t in temps:
        srow, irow = [], []
        for h in rhs:
            w = core.simplified_wbgt(t, h)
            srow.append(w)
            irow.append(bands.index(core.heat_band(w)["band"]))
        swbgt.append(srow); index.append(irow)

    reference = core.heat_band(30.0)
    # One representative sWBGT per band, so the action text is core's, never a paraphrase.
    actions = {b: core.heat_band(w)["action"] for b, w in zip(bands, [20.0, 25.0, 30.0, 34.0])}
    luteal = core.heat_risk(30.0, 50.0, luteal_phase=True).get("female_physiology_note")
    return {
        "generated_by": "wwc27_medagent.core.simplified_wbgt + core.heat_band",
        "package_version": core.__version__,
        "temp_c": {"min": HEAT_T_MIN, "max": HEAT_T_MAX, "step": HEAT_T_STEP},
        "rh_pct": {"min": HEAT_RH_MIN, "max": HEAT_RH_MAX, "step": HEAT_RH_STEP},
        "bands": bands,
        "actions": actions,
        "thresholds": reference["thresholds"],
        "source": reference["source"],
        "luteal_note": luteal,
        "swbgt": swbgt,
        "band_index": index,
    }


def main() -> int:
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(DATA / f, DOCS / "data" / f)
        json.loads((DOCS / "data" / f).read_text(encoding="utf-8"))   # fail loudly on bad JSON
    (DOCS / "data" / "venue_table.json").write_text(
        json.dumps(venue_rows(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (DOCS / "data" / "heat_grid.json").write_text(
        json.dumps(heat_grid(), ensure_ascii=False) + "\n", encoding="utf-8")
    option1 = OPTION1_LIVE.format(url=HOSTED_MCP_URL) if HOSTED_MCP_URL else OPTION1_PENDING
    other = OTHER_CLIENTS.replace("__URL__", HOSTED_MCP_URL or "(hosted endpoint not configured)")
    # No hosted service means no browser chat to link to; drop the card rather than ship a dead
    # link. The surviving cards then start at "Option 2", which is untidy but only reachable in
    # the state where Option 2 itself renders as "not yet available" and explains the gap.
    chat_card = CHAT_CARD.format(chat=HOSTED_CHAT_URL) if HOSTED_CHAT_URL else ""
    html = (HTML.replace("__CHATCARD__", chat_card)
                .replace("__OPTION1__", option1)
                .replace("__OTHERCLIENTS__", other)
                .replace("__REPO__", REPO)
                .replace("__DOI__", CONCEPT_DOI)
                .replace("__OUTLINE__", json.dumps(BRAZIL, separators=(",", ":")))
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
