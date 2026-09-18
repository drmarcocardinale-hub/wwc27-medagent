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
| `--max-instances 3`, `--concurrency 40` | A ceiling, so a runaway client cannot generate an unbounded bill. |
| `--memory 512Mi` | The server holds a few JSON files; it does not need more. |

## Check it worked

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

## Cost and keeping it honest

At scale-to-zero with this traffic the monthly cost is normally within the free allowance. Two
guards worth setting anyway, since the endpoint is public:

- a **budget alert** on the project (Billing → Budgets & alerts) so a surprise is caught early;
- `--max-instances`, already set to 3 above.

## If the build fails

`gcloud builds log --region <region>` shows the Cloud Build output. The usual causes are billing
not enabled on the project, or the APIs not yet active — the script enables them, but the first
enable can take a minute to propagate, so simply running it again often succeeds.
