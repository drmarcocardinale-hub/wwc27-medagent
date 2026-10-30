# Deploying the agent to Google Cloud Run

Cloud Run is the recommended host for the live endpoint. It scales to zero, so at the traffic a
paper's companion tool sees it costs close to nothing; the URL is stable; and it does not depend
on a free tier that can be withdrawn — which matters once the address is printed in an article.

## One command

```bash
cd ~/Documents/wwc27-medagent
gcloud config set project YOUR_PROJECT_ID     # once
./deploy/cloudrun/deploy.sh
```

The script enables the required APIs, builds the image from the repository `Dockerfile` with
Cloud Build (nothing is built on your machine, and Docker need not be installed), deploys it, and
prints the endpoint. Redeploying after a change is the same command.

To choose a region — closer to your users means a faster cold start:

```bash
REGION=southamerica-east1 ./deploy/cloudrun/deploy.sh   # São Paulo, nearest the tournament
```

## What the settings do, and why

| Setting | Why |
|---|---|
| `--allow-unauthenticated` | Readers must be able to connect without a Google account. The server is read-only, stores nothing and accepts no input beyond the query itself. |
| `MCP_STATELESS=1` | **The important one.** MCP's streamable HTTP transport keeps session state in the instance's memory. Cloud Run autoscales, so a follow-up request can arrive at a different instance, which then rejects the unknown session. Stateless mode makes every request self-contained. The only thing given up is server-initiated messages, which this server does not use. |
| `--session-affinity` | Best-effort stickiness, which helps any client that still prefers sessions. |
| `--min-instances 0` | Scale to zero. The first request after an idle period waits a few seconds for a cold start; set `--min-instances 1` to avoid that, at the cost of a small always-on charge. |
| `--max-instances 2`, `--concurrency 40` | A ceiling, so a runaway client cannot generate an unbounded bill. Two instances at 40 concurrent requests each is far more than this will ever need. |
| `--memory 512Mi` | The server holds a few JSON files; it does not need more. |
| `--update-env-vars`, **not** `--set-env-vars` | `--set` replaces the whole environment block, so a `GEMINI_API_KEY` set on the service by hand would be silently wiped by the next push and the chat would quietly start asking every visitor for their own key. `--update` merges. |
| `CHAT_FREE_PER_DAY=8`, `CHAT_GLOBAL_PER_DAY=150` | The chat's two rationing layers. See below. |
| `MCP_ALLOWED_HOSTS` (optional) | The MCP SDK enables DNS-rebinding protection and allows only localhost, so a hosted `/mcp` answers **421 Invalid Host header** to every client while a local probe still passes — which is exactly how it reached production unnoticed. Set this to the service's own hostname (comma separated; `name:*` allows any port) to keep the check on. Left unset, the check is turned off, which is defensible for this server — public, unauthenticated, read-only, no personal data, so rebinding gains an attacker nothing `curl` would not — and **not** defensible for one with private data or side effects. |

## Check it worked

The one to run after every deploy, from the repository root:

```bash
python3 scripts/check_deployed.py
```

It checks the service is up, that `/mcp` still answers and registers all nine tools, and then
asks the deployed agent three real questions — a single-tool one, the multi-city plan that has
broken in four different ways, and one it should refuse. It needs no API key, spends a few of the
instance's free questions, and exits non-zero on failure, so CI can run it too. Use `--quick` to
skip the questions.

This matters more than it looks. `pytest` runs the tool-calling loop against a stub, and the
stub cannot reproduce the real API: it does not attach a `thoughtSignature`, does not raise the
bare `TimeoutError` urllib raises, and does not take long enough to expose a timing budget. Every
fault that has reached a reader lived in that gap, and this script is what closes it.

### The low-level check

```bash
URL=$(gcloud run services describe wwc27-medagent --region europe-west1 --format 'value(status.url)')

curl -sS -X POST "$URL/mcp" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

A healthy reply names the server (`"name":"wwc27-medagent"`) and lists its capabilities. A `GET`
to the same path returning **406** is normal — the transport requires a POST with an
`Accept: text/event-stream` header.

## Connect a client

```bash
claude mcp add --transport http wwc27-medagent "$URL/mcp"
```

In Claude Desktop: Settings → Connectors → Add custom connector, and paste the same URL.

## After the first successful deploy

1. Put the endpoint into `scripts/build_site.py` as `HOSTED_MCP_URL`, then
   `python3 scripts/build_site.py` and commit — the site's "Ask it questions" tab then shows the
   address instead of "not yet available".
2. Add the endpoint to the manuscript's Data Availability statement, alongside the Zenodo DOI.

Keep the distinction clear when you write it up: **Zenodo is the archive of record** and is what
makes the work reproducible; the Cloud Run endpoint is convenience, and may move. Cite the DOI.

## Cost, and how to keep it at zero

Two separate meters run here, and only one of them is Google Cloud. Mixing them up is how a
free deployment turns into a bill.

### Cloud Run: effectively free at this traffic

The always-free monthly allowance is **180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million
requests** for request-based billing, aggregated per *billing account* and reset monthly. At
`--cpu 1 --memory 512Mi`, memory is not the binding constraint (360,000 ÷ 0.5 GiB = 720,000 s),
so the CPU allowance is: **180,000 seconds of request time a month.**

An MCP tool call returns in well under a second. A chat answer takes longer — perhaps 5–10
seconds, because the model is called once per tool-use round — and under request-based billing
CPU is allocated for the whole request, *including the time spent waiting for the model*. Even
so, at 8 seconds a question that is roughly **22,000 chat answers a month** inside the free
allowance. The `CHAT_GLOBAL_PER_DAY=150` ceiling below caps the month at ~4,500, about a fifth
of it.

`--min-instances 0` is what makes this true: an idle service that is not holding minimum
instances is not charged at all. Do not set `--min-instances 1` to avoid cold starts unless you
are willing to pay for an always-on instance.

### The model API: this is the one that can cost money

The chat calls the Gemini API with whatever key is in `GEMINI_API_KEY`, and that is billed by
Google separately from Cloud Run. The rationing in `chat.py` bounds it but does not guarantee it.

**The only hard guarantee is a key from an AI Studio project with no billing account linked.**
The Gemini API free tier does not require a billing account, and limits apply per project. With
no billing account there is nothing to charge: exceeding the free limits returns HTTP 429, which
the chat already turns into "the model API is rate limited right now", and the reader is invited
to supply their own key. Verify this before pointing readers at the page — a key created inside
a project that happens to have billing enabled will bill.

### The two rationing layers, and why one was not enough

| Layer | Default | What it stops |
|---|---|---|
| `CHAT_FREE_PER_DAY` | 8 per caller per day | A single enthusiastic reader working through the whole evidence table. |
| `CHAT_GLOBAL_PER_DAY` | 150 per instance per day | Everything the first layer cannot. A caller is an IP address, and an address is cheap: anything with a pool of them — a crawler, a scraper farm — collects 8 free questions *per address* and bills the house key for all of them. The global ceiling is what a rotating address cannot get past. |

Both are enforced in `take_free_question`, so there is one place to get it wrong rather than two.
A visitor who supplies their own key is not rationed at all, because it is not the house key
being spent. Hitting the global ceiling does not consume the refused caller's own allowance, and
both facts have tests (`tests/test_chat.py`).

Neither layer is the last line of defence; the absent billing account is. These exist so the free
allowance is not exhausted by lunchtime by something that is not a reader.

### Worth setting anyway

- A **budget alert** on the project (Billing → Budgets & alerts) — it catches a surprise early
  even when you believe nothing can bill.
- To turn the shared chat off entirely and have the page ask every visitor for their own key,
  remove `GEMINI_API_KEY` from the service. The page, the tables and `/mcp` all keep working:
  the chat is the only thing that depends on it.

## If the build fails

`gcloud builds log --region <region>` shows the Cloud Build output. The usual causes are billing
not enabled on the project, or the APIs not yet active — the script enables them, but the first
enable can take a minute to propagate, so simply running it again often succeeds.
