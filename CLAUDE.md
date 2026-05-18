# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment & commands

Always use the `ai-daily-digest-env` conda environment:

```bash
conda activate ai-daily-digest-env
```

Install/update dependencies:
```bash
pip install -r requirements.txt
```

Run the pipeline:
```bash
python run_digest.py              # full run: fetch, filter, rate, format, save, push
python run_digest.py --dry-run    # fetch + filter + rate without saving or committing
```

Regenerate `web/index.html` from existing `data/digests.json` without running the pipeline:
```bash
python web/generate.py
```

There is no test suite. Validate changes with `--dry-run`.

## Architecture

Data flows through five sequential stages in `run_digest.py`:

```
arxiv_source → dedup → filter → rater → formatter → data/digests.json → web/index.html
```

**Paper dict schema** — fields accumulate across stages:
- After fetch: `id`, `title`, `abstract`, `url`, `submitted_date`, `authors`, `source`, `affiliations`
- After filter: `+ filter_reason`
- After rater: `+ stars`, `rating_total`, `rating_rationale`
- After formatter: `+ description`, `contribution`, `limitations`, `links`, `date`

**`data/digests.json`** is the persistent store, keyed by ISO week (`"2026-W20"`). Each value is a list of up to `MAX_WEEKLY` (5) paper dicts. On every run, new candidates are merged with existing week papers and only the top 5 by `(stars, rating_total)` are kept — so the weekly digest self-improves across runs.

**`web/index.html`** is fully self-contained: `web/generate.py` inlines `web/style.css` and `web/app.js` and embeds the entire `digests.json` as a JS constant (`const DIGESTS = ...`). The frontend (`app.js`) renders paper cards and the sidebar entirely in vanilla JS from that constant.

**Affiliations** are fetched in two passes:
1. `sources/affiliations.py` calls the Semantic Scholar API for all candidates before filtering (cheap, bulk).
2. For papers that make the final cut and still lack affiliations, `fetch_affiliations_from_pdf` downloads and parses the PDF as a fallback (uses Claude Sonnet).

**Backfill** — on each run, `_get_missing_weeks` detects gaps in `digests.json` and calls `_backfill_week` for each, which reruns the full pipeline for that ISO week using `fetch_arxiv_papers(max_results=500, after=monday, before=sunday)`.

## Key customization points

All three AI prompts are module-level string constants — easy to edit in isolation:
- **`pipeline/filter.py` → `NOVELTY_PROMPT`**: controls what counts as novel enough to pass
- **`pipeline/rater.py` → `RATING_PROMPT`**: scoring rubric; the `topic` dimension (15% weight) is the primary personalization lever
- **`pipeline/formatter.py` → `OUTPUT_PROMPT`**: controls the output fields written to each paper card

Star thresholds and dimension weights live in `pipeline/rater.py` as `_WEIGHTS` and `_scores_to_stars`. Stars are always computed in Python from raw scores — the model never decides stars directly.

Arxiv categories: edit the `query` string in `sources/arxiv_source.py`. Common additions: `cs.RO`, `cs.CL`, `cs.NE`.

## Git workflow

After every code change, and after every call to `python run_digest.py`, commit and push to GitHub. Always pull before pushing.

```bash
git pull
git add <changed files>
git commit -m "<message>"
git push
```

Commit message format:
- After `python run_digest.py`: `digest: YYYY-MM-DD` (use the actual run date)
- After code changes: a short descriptive message summarizing what changed

## Models used

| Stage | Model | Notes |
|-------|-------|-------|
| Novelty filter | `claude-haiku-4-5` | ~100 calls/run |
| Rater | `claude-haiku-4-5` | ~10 calls/run |
| Formatter | `claude-sonnet-4-6` | ≤5 calls/run |
| PDF affiliation fallback | `claude-sonnet-4-6` | only for featured papers lacking affiliations |
