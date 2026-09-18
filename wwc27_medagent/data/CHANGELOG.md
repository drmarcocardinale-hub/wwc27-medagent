# WWC27-MedAgent curation log

Each release is tagged, re-tested (`pytest`), and archived. Curators: Marco Cardinale, Celeste Geertsema [confirm].

## 0.2.0 — 2026-09-18
- Air quality added: per-city profiles (typical sources, June–July pattern, monitoring agency), WHO 2021 guideline levels, Brazil's CONAMA 506/2024 staged standards, and author-defined PM2.5 planning bands for training and match decisions.
- New tools: `get_air_quality` (optionally fetching current concentrations from the Open-Meteo/CAMS API when the host machine has internet access) and `plan_respiratory_care` (PM2.5 band plus asthma/EIB screening, management and 2026 anti-doping limits for inhaled beta-2 agonists).
- New resource `wwc27://air-quality`; new Table 2 domain "Airway health, asthma/EIB and air quality"; six new evidence items (E34–E39).
- `scripts/refresh_air_quality.py` fills the June–July climatology from the Open-Meteo archive; not yet run in this release (no network access at build time), so `climatology` is null and the tools say so.
- Benchmark grown from 50 to 61 items (25/13/11/12); 54 automated tests.

## 0.1.0 — 2026-09-17 (manuscript submission draft)
- Initial evidence table (33 claims, 43 references) covering men's World Cups (2014, 2022, 2026), Women's World Cups (2019, 2023), female athlete health consensus statements and Brazil travel health.
- Host-city climate normals (INMET), elevation, and CDC Yellow Book 2026 yellow-fever guidance.
- Tools: venue profile, heat-risk estimate, travel burden, screening checklist, evidence lookup, tournament facts.
- Evidence retrieval uses whole-word matching; generic context words (e.g. "team", "women") do not count on their own; a year named in the question must match the evidence item.
- Validation: 41 automated tests; 50-item benchmark (20 reproduction, 10 application, 10 open-ended, 10 out-of-scope) with tool-layer check, end-to-end evaluation harness and blinded rating workflow.
- Archived on GitHub + Zenodo (see RELEASING.md).
- Known gaps to fill: peer-reviewed surveillance from the 2026 men's World Cup; kick-off times and base camps (after the final draw); 2027 arbovirus bulletins.

## Update triggers (living mode)
- New peer-reviewed tournament surveillance or consensus statement relevant to a domain in Table 2.
- FIFA schedule changes (kick-off times, venues) or heat-policy changes.
- Public-health notices for host states (dengue, Oropouche, yellow fever, measles, respiratory viruses).
- Air-quality updates: re-run scripts/refresh_air_quality.py, and check the state monitoring agencies and any WHO/CONAMA changes.
- Annual anti-doping list changes (inhaled beta-2 agonist limits).
- Monthly check from January 2027 and weekly from May 2027 until the final.
