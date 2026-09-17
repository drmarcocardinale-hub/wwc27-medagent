# WWC27-MedAgent curation log

Each release is tagged, re-tested (`pytest`), and archived. Curators: Marco Cardinale, Celeste Geertsema [confirm].

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
- Monthly check from January 2027 and weekly from May 2027 until the final.
