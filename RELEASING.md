# Publishing on GitHub and archiving on Zenodo

This takes about 20 minutes the first time. Afterwards, every GitHub release gets its own Zenodo DOI automatically.

## 1. Create the GitHub repository
1. On github.com, create a new **public** repository named `wwc27-medagent`. Leave it empty: no README, licence or .gitignore.
2. In a terminal inside this folder (a git repository with an initial commit is already set up), run:
   ```bash
   git remote add origin https://github.com/<OWNER>/wwc27-medagent.git
   git branch -M main
   git push -u origin main
   ```
3. Replace `OWNER` in `CITATION.cff` and `README.md`, then commit and push.
4. Open the **Actions** tab and check that the `tests` workflow passes (green tick).

## 2. Connect Zenodo (do this once, before the first release)
1. Sign in at https://zenodo.org with your GitHub account (use ORCID too if you have it).
2. Go to **Account → GitHub**, click **Sync now**, and switch **wwc27-medagent** to *On*.
3. Zenodo will read `.zenodo.json` for the title, authors, licence and keywords. Add your ORCIDs there first if you want them on the record.

## 3. Make the first release (v0.1.0, the manuscript submission version)
1. On GitHub, go to **Releases → Draft a new release**. Tag `v0.1.0`, title "v0.1.0 – submission version", and paste in the changelog entry.
2. Publish the release. Within a few minutes Zenodo will mint two DOIs:
   - a **version DOI** for v0.1.0: cite this one in the manuscript's Code Availability statement;
   - a **concept DOI** that always resolves to the latest version: use it in the article text as the "living" link.
3. Add the Zenodo DOI badge to the README, then commit.

## 4. Living-mode updates
- Follow the curation steps in the README. Every change needs its tests to pass on GitHub Actions before release.
- Use version numbers as follows:
  - patch (0.1.x): data corrections;
  - minor (0.x.0): new evidence or new tools;
  - major: changes to the benchmark or the framework.
- Each release gets its own version DOI. The concept DOI in the article always points to the newest one.
- Upload end-to-end benchmark outputs (`benchmark/results/`) as release assets so the evaluation can be reproduced.

## 5. Optional remote hosting
Some teams will want to connect without installing Python. For them, the included `Dockerfile` runs the server over HTTP (for example as a Hugging Face Space or on an institutional server). GitHub and Zenodo remain the archive of record.
