"""The Space's single ASGI app: a chat page at /, the MCP endpoint still at /mcp.

One container, two surfaces. The MCP endpoint keeps its path and behaviour because it is the
thing cited in the paper; the chat is mounted in front of it and must never be able to change
what /mcp answers. The MCP app's lifespan is passed through explicitly - Starlette does not run
a mounted app's lifespan, and without it the session manager never starts and every MCP request
fails with a 500 that looks nothing like its cause.
"""
from __future__ import annotations

import json
import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from . import chat, core

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ask WWC27-MedAgent</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%230b6b5e'/%3E%3C/svg%3E">
<style>
:root{
  --bg:#faf9f7; --surface:#fff; --surface-2:#f5f3ef; --line:#e4e0da; --line-soft:#efece6;
  --ink:#1c1a17; --ink-2:#47423b; --muted:#6b645c; --accent:#0b6b5e; --accent-soft:#e6f2f0;
  --warn:#cf7a12; --warn-soft:#fbeeda; --radius:12px; --radius-sm:8px;
  --shadow:0 1px 2px rgba(28,26,23,.05), 0 8px 24px -16px rgba(28,26,23,.18);
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#141619; --surface:#1e2124; --surface-2:#252a2e; --line:#32373c; --line-soft:#282d31;
  --ink:#e9e6e1; --ink-2:#c2bdb6; --muted:#9aa0a6; --accent:#5fd3bf; --accent-soft:#16302c;
  --warn:#c08a1a; --warn-soft:#332714;
  --shadow:0 1px 2px rgba(0,0,0,.30), 0 8px 24px -16px rgba(0,0,0,.60);
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55}
.wrap{max-width:820px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line);background:
  radial-gradient(120% 140% at 12% -10%, var(--accent-soft) 0%, transparent 58%), var(--surface)}
header .wrap{padding:24px 20px 18px}
.eyebrow{font-size:.72rem;letter-spacing:.11em;text-transform:uppercase;color:var(--accent);
  font-weight:700;margin:0 0 8px}
h1{font-size:1.5rem;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--ink-2);margin:0;font-size:.92rem;max-width:62ch}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 10px;
  color:var(--muted);text-decoration:none;background:var(--surface);font-size:.78rem;margin:10px 6px 0 0}
.pill:hover{border-color:var(--accent);color:var(--accent)}
.note{background:var(--warn-soft);border-left:3px solid var(--warn);padding:10px 14px;
  border-radius:0 var(--radius-sm) var(--radius-sm) 0;font-size:.85rem;margin:16px 0}
main{padding:20px 0 40px}
#log{display:flex;flex-direction:column;gap:12px;margin-bottom:16px}
.msg{padding:12px 15px;border-radius:var(--radius);max-width:46rem}
.msg.you{background:var(--accent-soft);align-self:flex-end;border:1px solid var(--line-soft)}
.msg.bot{background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow)}
.msg p{margin:0 0 .6em}.msg p:last-child{margin:0}
.msg ul,.msg ol{margin:.3em 0 .6em;padding-left:1.3em}.msg li{margin-bottom:.25em}
.msg a{color:var(--accent)}
.trace{margin-top:9px;padding-top:8px;border-top:1px solid var(--line-soft);font-size:.76rem;
  color:var(--muted);font-family:var(--mono)}
.trace b{font-weight:600;color:var(--ink-2)}
form{display:flex;gap:8px;align-items:flex-end}
textarea{flex:1;font:inherit;font-size:.95rem;padding:11px 13px;border:1px solid var(--line);
  border-radius:var(--radius);background:var(--surface);color:var(--ink);resize:vertical;
  min-height:52px;max-height:200px}
textarea:focus{outline:2px solid var(--accent);outline-offset:1px}
button{font:inherit;font-weight:600;padding:12px 18px;border:1px solid var(--line);
  border-radius:var(--radius);background:var(--accent-soft);color:var(--accent);cursor:pointer}
button:hover:not(:disabled){border-color:var(--accent)}
button:disabled{opacity:.55;cursor:default}
.status{font-size:.8rem;color:var(--muted);margin:10px 0 0;min-height:1.2em}
.examples{display:flex;flex-wrap:wrap;gap:7px;margin:0 0 16px}
.examples button{font-size:.8rem;font-weight:400;padding:6px 11px;border-radius:999px;
  background:var(--surface);color:var(--ink-2)}
#keybox{display:none;margin-top:14px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow)}
#keybox.show{display:block}
#keybox input{width:100%;font:inherit;font-family:var(--mono);font-size:.85rem;padding:9px 11px;
  border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--bg);
  color:var(--ink);margin:8px 0}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.8rem;padding:18px 0 36px}
.spin{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);
  margin-right:7px;animation:p 1.1s ease-in-out infinite}
@keyframes p{0%,100%{opacity:.25}50%{opacity:1}}
@media (prefers-reduced-motion:reduce){.spin{animation:none}}
</style>
</head>
<body>
<header><div class="wrap">
  <p class="eyebrow">Paper agent &middot; v__VERSION__</p>
  <h1>Ask WWC27-MedAgent</h1>
  <p class="sub">Host-city conditions, the screening and monitoring matrix and a source-linked
  evidence base for the FIFA Women's World Cup Brazil 2027. Every answer here is produced by
  calling the same tools an MCP client would call, and each one carries its source.</p>
  <a class="pill" href="https://drmarcocardinale-hub.github.io/wwc27-medagent/">Reader site</a>
  <a class="pill" href="https://github.com/drmarcocardinale-hub/wwc27-medagent">Code</a>
  <a class="pill" href="https://doi.org/10.5281/zenodo.22832165">Archive DOI</a>
  <a class="pill" href="/mcp">MCP endpoint</a>
  <div class="note"><strong>Decision support only, and not private.</strong> This summarises
  published evidence and climate normals; it does not replace clinical judgement, on-site WBGT
  measurement or current public-health advice. Questions are sent to Google's Gemini API to be
  answered. <strong>Do not enter player names or any identifiable detail.</strong></div>
</div></header>

<main><div class="wrap">
  <div class="examples" id="examples"></div>
  <div id="log"></div>
  <form id="form">
    <textarea id="q" rows="2" placeholder="Ask about a host city, the heat bands, screening, travel or the evidence base&hellip;" aria-label="Your question"></textarea>
    <button type="submit" id="send">Ask</button>
  </form>
  <p class="status" id="status"></p>
  <div id="keybox">
    <strong style="font-size:.92rem">Out of free questions for today</strong>
    <p style="font-size:.85rem;color:var(--muted);margin:6px 0 0">Carry on with your own Gemini
    API key from <a href="https://aistudio.google.com/apikey">aistudio.google.com/apikey</a>. It
    is held in this browser tab for this session only, sent with each question and never stored
    on the server.</p>
    <input type="password" id="key" placeholder="AIza&hellip;" autocomplete="off" spellcheck="false">
    <button type="button" id="savekey">Use this key</button>
  </div>
</div></main>

<footer><div class="wrap">
  Data CC BY 4.0, code MIT. Cite the article and the archived release. The reader site and the
  Zenodo archive answer the same questions without this chat.
</div></footer>

<script>
const log = document.getElementById("log"), statusEl = document.getElementById("status");
const form = document.getElementById("form"), q = document.getElementById("q");
const send = document.getElementById("send"), keybox = document.getElementById("keybox");
let history = [], userKey = "", busy = false;

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// Deliberately tiny: bold, links, paragraphs and bullets. Anything more would mean trusting
// model output with innerHTML, and everything is escaped before these run.
function render(md){
  let h = esc(md)
    .replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>")
    .replace(/(https?:\\/\\/[^\\s<)]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  const lines = h.split(/\\n/), out = []; let list = null;
  for (const line of lines){
    const m = line.match(/^\\s*[-*]\\s+(.*)$/);
    if (m){ (list = list || []).push("<li>" + m[1] + "</li>"); continue; }
    if (list){ out.push("<ul>" + list.join("") + "</ul>"); list = null; }
    if (line.trim()) out.push("<p>" + line + "</p>");
  }
  if (list) out.push("<ul>" + list.join("") + "</ul>");
  return out.join("");
}

function bubble(cls, html){
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.innerHTML = html;
  log.appendChild(d);
  d.scrollIntoView({behavior: "smooth", block: "end"});
  return d;
}

async function ask(text){
  if (busy || !text.trim()) return;
  busy = true; send.disabled = true;
  bubble("you", "<p>" + esc(text) + "</p>");
  history.push({role: "user", text: text});
  statusEl.innerHTML = '<span class="spin"></span>Calling the tools&hellip;';
  try {
    const r = await fetch("api/chat", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({history: history, key: userKey})
    });
    const data = await r.json();
    if (!r.ok){
      if (data.need_key){ keybox.classList.add("show"); }
      statusEl.textContent = "";
      bubble("bot", "<p>" + esc(data.error || "Something went wrong.") + "</p>");
    } else {
      history.push({role: "model", text: data.answer});
      const seen = [...new Set((data.tools || []).map(t => t.name))];
      const trace = seen.length
        ? '<div class="trace"><b>tools called:</b> ' + esc(seen.join(", ")) + "</div>" : "";
      bubble("bot", render(data.answer) + trace);
      statusEl.textContent = data.free_left != null && !userKey
        ? data.free_left + " free question" + (data.free_left === 1 ? "" : "s") + " left today"
        : "";
    }
  } catch (e){
    statusEl.textContent = "";
    bubble("bot", "<p>" + esc("Could not reach the server: " + e.message) + "</p>");
  }
  busy = false; send.disabled = false; q.focus();
}

form.addEventListener("submit", e => { e.preventDefault(); const t = q.value; q.value = ""; ask(t); });
q.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey){ e.preventDefault(); form.requestSubmit(); }
});
document.getElementById("savekey").addEventListener("click", () => {
  userKey = document.getElementById("key").value.trim();
  if (userKey){ keybox.classList.remove("show"); statusEl.textContent = "Using your own key."; }
});

const EXAMPLES = [
  "What's the heat band for Salvador in July?",
  "We're based in Sao Paulo and play in Fortaleza, Recife and Porto Alegre. Draft our pre-tournament medical plan.",
  "What did the 2023 Women's World Cup show about illness?",
  "Which host cities need yellow fever vaccination?"
];
document.getElementById("examples").innerHTML =
  EXAMPLES.map(t => '<button type="button">' + esc(t) + "</button>").join("");
document.querySelectorAll("#examples button").forEach(b =>
  b.addEventListener("click", () => ask(b.textContent)));

fetch("api/meta").then(r => r.json()).then(m => {
  if (!m.house_key){
    keybox.classList.add("show");
    statusEl.textContent = "This instance has no shared key, so bring your own to ask anything.";
  } else {
    statusEl.textContent = m.free_per_day + " free questions a day, then your own key.";
  }
}).catch(() => {});
</script>
</body>
</html>
"""


def _caller(request: Request) -> str:
    """Best available caller identity behind a proxy. Not security, just rationing."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def page(request: Request) -> HTMLResponse:
    return HTMLResponse(PAGE.replace("__VERSION__", core.__version__))


async def meta(request: Request) -> JSONResponse:
    return JSONResponse({"version": core.__version__, "model": chat.MODEL,
                         "house_key": bool(chat.house_key()),
                         "free_per_day": chat.FREE_PER_DAY,
                         "free_left": chat.free_left(_caller(request))})


async def healthz(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def api_chat(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Expected JSON."}, status_code=400)

    history = body.get("history") or []
    if not isinstance(history, list) or not history:
        return JSONResponse({"error": "No question."}, status_code=400)
    turns = [{"role": "model" if h.get("role") == "model" else "user",
              "text": str(h.get("text", ""))[:chat.MAX_CHARS]} for h in history]
    if not turns[-1]["text"].strip():
        return JSONResponse({"error": "No question."}, status_code=400)

    caller = _caller(request)
    own = str(body.get("key") or "").strip()
    if own:
        key = own                                    # their key, their quota, no rationing
    else:
        key = chat.house_key()
        if not key:
            return JSONResponse({"error": "This instance has no shared key. Add your own Gemini "
                                          "API key to ask questions.", "need_key": True},
                                status_code=402)
        if not chat.take_free_question(caller):
            # Which ceiling was hit changes what the visitor should do about it, so say which.
            exhausted = chat.global_left() <= 0
            message = ("This instance has answered all of today's shared questions. Add your own "
                       "Gemini API key to carry on, or come back tomorrow."
                       if exhausted else
                       f"That's the {chat.FREE_PER_DAY} free questions for today. Add your own "
                       "Gemini API key to carry on.")
            return JSONResponse({"error": message, "need_key": True}, status_code=429)

    try:
        result = await chat.answer(turns, key)
    except chat.ChatError as exc:
        return JSONResponse({"error": str(exc)}, status_code=exc.status)
    except Exception as exc:                          # never leak a traceback to the page
        return JSONResponse({"error": f"The agent failed: {type(exc).__name__}."},
                            status_code=500)

    result["free_left"] = chat.free_left(caller) if not own else None
    return JSONResponse(result)


def build_app():
    """Chat routes first, the MCP app mounted behind them so /mcp keeps its path."""
    from .server import mcp
    stateless = os.environ.get("MCP_STATELESS", "").lower() in ("1", "true", "yes")
    try:
        mcp_app = mcp.streamable_http_app(stateless_http=stateless)
    except TypeError:                                 # mcp 1.x takes it off .settings instead
        try:
            mcp.settings.stateless_http = stateless
        except Exception:
            pass
        mcp_app = mcp.streamable_http_app()

    routes = [
        Route("/", page),
        Route("/healthz", healthz),
        Route("/api/meta", meta),
        Route("/api/chat", api_chat, methods=["POST"]),
        Mount("/", app=mcp_app),
    ]
    # Starlette does not run a mounted app's lifespan; the MCP session manager lives in it.
    lifespan = getattr(getattr(mcp_app, "router", None), "lifespan_context", None)
    return Starlette(routes=routes, lifespan=lifespan)


def main() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(build_app(), host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
