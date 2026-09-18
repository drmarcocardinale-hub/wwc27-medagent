# WWC27-MedAgent validation benchmark

The benchmark follows the evaluation design of Paper2Agent (Miao et al., *Nature* 2026). It tests whether the agent reproduces what the article reports, applies the article's tools to new questions, gives useful answers to open clinical scenarios, and declines questions its evidence base cannot answer.

## Item sets (`questions.jsonl`, 61 items)

| Set | n | What it tests | Ground truth | Scoring |
|---|---|---|---|---|
| A · reproduction | 25 | Single facts from Tables 1–2 and the cited sources (climate, dates, injury/illness rates, prevention effects, air-quality guideline levels, anti-doping limits) | Computed from the versioned data files | Automatic (numeric tolerance) |
| B · application | 13 | New questions that need tool computation or composition (itinerary distances, sWBGT from a forecast, PM2.5 planning bands, venue-specific heat, air-quality or vaccine status) | Computed with the tools from the data files | Automatic (numeric tolerance, relative ±2% for distances; exact set match) |
| C · open-ended | 11 | Practitioner scenarios (e.g. a pre-tournament plan for a given base camp and fixtures; luteal phase in a hot match; low ferritin) | 4–7 rubric elements per item, each linked to sources | Two blinded raters mark each element present (1) or absent (0) |
| D · out-of-scope | 12 | Questions outside the evidence base, including tempting near-misses (2015 Women's World Cup injury rates, a future WBGT, kick-off times) | Declining to answer | Automatic (refusal detection) |

Regenerate the file with `python benchmark/build_benchmark.py`. `tests/test_benchmark.py` fails if the file is out of date with the data.

## Protocol

1. **Tool-layer check (no language model).** Run `python benchmark/run_tool_check.py`. It confirms that every A/B ground truth can be reached through the tools and records whether retrieval declines each D item. It also runs a 20-question held-out retrieval check (`retrieval_holdout.json`).
2. **End-to-end evaluation.** Run `python benchmark/run_agent_eval.py --model <id> --runs 5`. Each item is asked five times under three conditions:
   - **agent**: the MCP tools only;
   - **paper_in_context**: the full manuscript in the prompt, no tools;
   - **closed_book**: neither tools nor manuscript.
   
   The script records answers, tool calls, latency and token use.
3. **Automatic scoring and rater sheets.** Run `python benchmark/score.py results/responses_<stamp>.jsonl`. It reports accuracy for sets A, B and D as the mean ± s.e.m. across runs, and writes two blinded rater sheets for set C. Condition labels are replaced by random codes, and the key is kept separately.
4. **Human rating.** Two sports-medicine physicians who did not write the rubric rate each element independently. Then run `python benchmark/score.py results/responses_<stamp>.jsonl --ratings rater1.csv rater2.csv`. It reports percent agreement, Cohen's κ, and the rubric score for each condition (mean ± s.e.m. across runs). The raters discuss disagreements afterwards; report both the pre-discussion agreement and the final scores.
5. **Reporting.** State the model identifier and date, the benchmark version (the git tag), the number of runs, and any items removed with the reason. Archive the raw responses with the Zenodo release.

## Development status (v0.2.0, 18 Sep 2026)

- **Tool layer:** 38/38 A/B ground truths are reachable.
- **Retrieval layer:**
  - Set D: 12/12 declined. The retrieval rules were revised while set D was being written, so treat set D as a development set.
  - Held-out retrieval check (run once, no tuning afterwards): 7/10 in-scope questions returned the expected evidence in the top three, and 7/10 out-of-scope questions were declined.
  - Most misses involve synonyms ("painkillers" rather than "NSAIDs") or generic words ("meal", "airline", "coach"). The language model is expected to handle these, and the end-to-end run tests whether it does.
- **Pipeline:** self-tested with `--mock oracle`, which gives 100% by construction and only confirms that the pipeline runs.
- **End-to-end results:** not yet run. The run needs an Anthropic API key and two raters.
