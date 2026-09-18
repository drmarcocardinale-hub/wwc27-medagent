#!/usr/bin/env bash
# Deploy WWC27-MedAgent to Google Cloud Run.
#
# Why Cloud Run rather than a free Space: it scales to zero (so it costs about nothing at this
# traffic), the URL is stable, and it will not be withdrawn when a free tier changes - which
# matters for an endpoint cited in a paper.
#
#   ./deploy/cloudrun/deploy.sh                     # first deploy, or redeploy after changes
#   PROJECT=my-project REGION=europe-west1 ./deploy/cloudrun/deploy.sh
#
# Needs the gcloud CLI, authenticated, with billing enabled on the project. Nothing is built
# locally: Cloud Build reads the Dockerfile in the repository root.
set -euo pipefail

SERVICE="${SERVICE:-wwc27-medagent}"
REGION="${REGION:-europe-west1}"

# Check for the CLI before anything else. Without this the script dies silently: `set -e` plus a
# command substitution on a missing command exits before the friendly message can be printed.
if ! command -v gcloud >/dev/null 2>&1; then
  cat >&2 <<'MSG'
gcloud is not installed (or not on PATH).

Install it, then open a NEW terminal window so PATH picks it up:

  Official installer (works on any Mac):
      curl https://sdk.cloud.google.com | bash

  Or with Homebrew, if you have it:
      brew install --cask google-cloud-sdk

Then:
      gcloud init          # sign in and choose the project
      bash deploy/cloudrun/deploy.sh

If you have just installed it and this message persists, the PATH is not set for this shell:
      exec -l $SHELL
MSG
  exit 127
fi

PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "No project set. Run:  gcloud config set project YOUR_PROJECT_ID" >&2
  echo "or:                   PROJECT=YOUR_PROJECT_ID $0" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

echo "Project : ${PROJECT}"
echo "Region  : ${REGION}"
echo "Service : ${SERVICE}"
echo "Source  : ${ROOT}"
echo

echo "Enabling the APIs this needs (no-op if already on)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com --project "${PROJECT}" --quiet

echo
echo "Building and deploying..."
# --allow-unauthenticated: readers must be able to connect without a Google account.
#   The server is read-only, holds no personal data and takes no input beyond the query.
# MCP_STATELESS=1: streamable HTTP keeps session state in memory, and Cloud Run may send the
#   next request to a different instance. Stateless mode makes each request self-contained.
# --min-instances 0: scale to zero. First request after idle waits a few seconds for a cold start.
# --session-affinity: best-effort stickiness, which helps clients that do use sessions.
gcloud run deploy "${SERVICE}" \
  --source . \
  --project "${PROJECT}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "MCP_STATELESS=1" \
  --port 8080 \
  --cpu 1 --memory 512Mi \
  --min-instances 0 --max-instances 3 \
  --concurrency 40 \
  --timeout 300 \
  --session-affinity \
  --quiet

URL="$(gcloud run services describe "${SERVICE}" --project "${PROJECT}" \
        --region "${REGION}" --format 'value(status.url)')"

echo
echo "================================================================"
echo "  Deployed."
echo "  MCP endpoint:  ${URL}/mcp"
echo "================================================================"
echo
echo "Check it:"
echo "  curl -sS -X POST ${URL}/mcp \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'Accept: application/json, text/event-stream' \\"
echo "    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"curl\",\"version\":\"1\"}}}'"
echo
echo "Connect Claude Code:"
echo "  claude mcp add --transport http wwc27-medagent ${URL}/mcp"
echo
echo "Then set HOSTED_MCP_URL in scripts/build_site.py to that endpoint and rebuild the site."
