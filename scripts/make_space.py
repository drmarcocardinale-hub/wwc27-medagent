"""Assemble a ready-to-push Hugging Face Space in build/space/.

A Space is its own git repository whose root README.md must carry Hugging Face's YAML
frontmatter. That frontmatter would be wrong at the top of the project README, so rather than
contort this repository, the Space is assembled into build/space/ with the right README and only
the files the server needs.

    python scripts/make_space.py

The owner and Space name are set below (HF_USER, SPACE_NAME); the README and the endpoint are
generated from them, so there is nothing to fill in by hand. Then, once:

    1. Create the Space at https://huggingface.co/new-space
       - Owner: the same account as HF_USER      - Space name: SPACE_NAME below
       - SDK: Docker (Blank template)            - Hardware: CPU basic (free)
       - Visibility: Public
    2. Either upload build/space/ through the Space's Files tab, or:
       cd build/space
       git init && git add -A && git commit -m "WWC27-MedAgent MCP server"
       git branch -M main
       git remote add origin https://huggingface.co/spaces/<HF_USER>/<SPACE_NAME>
       git push -u origin main          # username = HF username, password = a WRITE access token
    3. Watch the build log on the Space page. When it goes green, the endpoint is
       https://<HF_USER>-<SPACE_NAME>.hf.space/mcp

Renaming the Space later changes that URL, which matters once it is cited in a paper.

Connect an MCP client to that URL. Free Spaces sleep after ~48 h idle and wake on the next
request, so the first call after a quiet spell is slow. Nothing here stores data or takes user
input beyond the query itself, and the server is read-only.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "space"

# Hugging Face username that owns the Space. The endpoint is derived from it, so
# changing this (or renaming the Space) changes the published URL.
HF_USER = "marcocardi"
SPACE_NAME = "wwc27-medagent"

# Only what the server needs at runtime. The benchmark, tests, docs and site stay in the
# GitHub repository; the Space is the live endpoint, not a second copy of the project.
COPY = ["wwc27_medagent", "pyproject.toml", "LICENSE", "Dockerfile"]

README = """---
title: WWC27-MedAgent
emoji: ⚕️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Medical preparation agent for the 2027 Women's World Cup
---

# WWC27-MedAgent

A **Model Context Protocol (MCP) server** carrying the evidence base, host-city data and
screening matrix from the Current Opinion *"Sports Medicine and Science Considerations to
Maximise Preparation for the FIFA Women's World Cup Brazil 2027: From Static Evidence to a
Living Agent"* (Cardinale & Geertsema, submitted to *Sports Medicine*).

It follows the Paper2Agent model (Miao et al., *Nature* 2026,
[doi:10.1038/s41586-026-11044-y](https://doi.org/10.1038/s41586-026-11044-y)).

> **Decision support only.** Outputs summarise published evidence and climate normals. They do
> not replace clinical judgement, on-site WBGT measurement or current public-health advice.
> **Do not enter identifiable player data.**

## Connect to it

The endpoint is `https://{hf}-wwc27-medagent.hf.space/mcp` (streamable HTTP).

**Claude Code**
```bash
claude mcp add --transport http wwc27-medagent https://{hf}-wwc27-medagent.hf.space/mcp
```

**Claude Desktop** — Settings → Connectors → Add custom connector, and paste the same URL.

Then ask, in plain language:

- *"We're based in São Paulo and play in Fortaleza, Recife and Porto Alegre. Draft our
  pre-tournament medical plan."*
- *"The Salvador forecast is 28 °C and 85% humidity and three starters are likely luteal.
  What's the heat band and what should we do?"*
- *"What did the 2023 Women's World Cup show about illness?"*

## What it exposes

Nine tools (venue profile, heat risk, travel burden, screening checklist, air quality,
respiratory care, air-quality sources, evidence search, tournament facts), seven machine-readable
resources and two guided prompts. Evidence search answers **"I don't know"** when a question
falls outside the curated evidence base rather than improvising.

## Browse without an AI client

The same tables as a plain web page: <https://drmarcocardinale-hub.github.io/wwc27-medagent/>

## Source, archive and citation

- Code: <https://github.com/drmarcocardinale-hub/wwc27-medagent> (MIT; data tables CC BY 4.0)
- Archive: [10.5281/zenodo.22832165](https://doi.org/10.5281/zenodo.22832165) — concept DOI,
  always resolves to the current version

This Space runs whichever release was pushed to it. The archived release is the version of
record; cite that.
"""


def main() -> int:
    # Overwrite in place rather than deleting first: this folder may sit on a mount where
    # unlink is not permitted, and a failed rmtree there leaves a half-removed bundle.
    OUT.mkdir(parents=True, exist_ok=True)
    before = {f.relative_to(OUT) for f in OUT.rglob("*") if f.is_file()}
    for item in COPY:
        src = ROOT / item
        if not src.exists():
            raise SystemExit(f"missing {item}")
        if src.is_dir():
            shutil.copytree(src, OUT / item, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "airq_archive"))
        else:
            shutil.copy2(src, OUT / item)
    readme = README.format(hf=HF_USER)
    # Hugging Face rejects the upload if this exceeds 60 characters, and the error only shows
    # after the files are already on the Space, so check it before writing.
    for line in readme.splitlines():
        if line.startswith("short_description:"):
            value = line.split(":", 1)[1].strip()
            if len(value) > 60:
                raise SystemExit(f"short_description is {len(value)} characters; "
                                 f"Hugging Face allows 60:\n  {value}")
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    (OUT / ".gitattributes").write_text("*.json text\n*.md text\n", encoding="utf-8")
    (OUT / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.DS_Store\n", encoding="utf-8")

    written = {f.relative_to(OUT) for f in OUT.rglob("*") if f.is_file()}
    stale = sorted(f for f in (before - written) if "__pycache__" not in str(f))
    if stale:
        print("Note: left over from an earlier build, not part of the bundle:")
        for f in stale:
            print(f"  {f}")
    n = sum(1 for _ in OUT.rglob("*") if _.is_file() and "__pycache__" not in str(_))
    mb = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1e6
    print(f"build/space/ assembled: {n} files, {mb:.1f} MB")
    print("\nNext:")
    print("  1. Create a Docker Space at https://huggingface.co/new-space (name: wwc27-medagent)")
    print("  2. cd build/space && git init && git add -A && git commit -m 'WWC27-MedAgent'")
    print(f"     git remote add origin https://huggingface.co/spaces/{HF_USER}/{SPACE_NAME}")
    print("     git push -u origin main")
    print(f"\n  Endpoint once it is running:  https://{HF_USER}-{SPACE_NAME}.hf.space/mcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
