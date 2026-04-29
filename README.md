# Johanna's AI Daily Digest

An agentic pipeline that fetches recent ML papers from arxiv, filters them for novelty, rates them by impact and personal relevance, and publishes a weekly digest as a static webpage — updated automatically every time the script runs.

**Live site:** https://johannakarras.github.io/AIDailyDigest/

---

## How it works

Each run of `run_digest.py` does the following:

1. **Fetch** — pulls up to 100 papers from the past 7 days across `cs.CV`, `cs.LG`, and `cs.AI` on arxiv
2. **Deduplicate** — skips papers already seen in any past digest; drops papers older than 14 days
3. **Filter** — uses `claude-haiku-4-5` to reject incremental/survey papers and pass genuinely novel ones (~10–15% pass rate)
4. **Rate** — scores each passing paper on 7 dimensions (see [Customizing the rater](#customizing-the-rater)); stars are computed in Python from raw dimension scores
5. **Rank & select** — merges new candidates with the current week's existing papers, keeps the top 5 by rating
6. **Format** — uses `claude-sonnet-4-6` to write a one-sentence description, novel contribution, and limitations for each new paper that earned a spot
7. **Save & publish** — writes `data/digests.json`, regenerates `web/index.html`, commits both, and pushes to GitHub (triggering a GitHub Pages redeploy)

Papers are organized by ISO week (`YYYY-Www`). Running the script multiple times in a week will swap in better papers if they appear — the weekly digest converges on the best 5 papers found that week.

---

## Setup

### Prerequisites

- [Anaconda or Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- An [Anthropic API key](https://console.anthropic.com/)
- Git

### 1. Clone and create the environment

```bash
git clone https://github.com/johannakarras/AIDailyDigest.git
cd AIDailyDigest

conda create -n ai-daily-digest-env python=3.11 -y
conda activate ai-daily-digest-env
pip install -r requirements.txt
```

### 2. Add your API key

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run

```bash
conda activate ai-daily-digest-env
python run_digest.py
```

Open `web/index.html` in a browser to view the digest locally.

Add `--dry-run` to fetch and filter without saving anything:

```bash
python run_digest.py --dry-run
```

---

## Publishing to GitHub Pages

1. Fork this repo and push your changes to `main`
2. Go to **Settings → Pages** in your fork and set the source to **GitHub Actions**
3. The `.github/workflows/pages.yml` workflow deploys `web/` automatically on every push that changes `web/index.html`

Your digest will be live at `https://<your-username>.github.io/AIDailyDigest/`.

---

## Customizing

### Arxiv categories

Edit `sources/arxiv_source.py` to change which arxiv categories are fetched:

```python
query = "cat:cs.CV OR cat:cs.LG OR cat:cs.AI"
```

Common additions: `cs.RO` (robotics), `cs.CL` (NLP), `cs.NE` (neural/evolutionary computation), `eess.IV` (image processing).

### Novelty filter

Edit `NOVELTY_PROMPT` in `pipeline/filter.py` to change what counts as novel. The current filter passes papers that propose new architectures, new capabilities, new theoretical framings, or surprising empirical findings — and rejects surveys, fine-tuning on new datasets, and incremental benchmarking.

### Customizing the rater

The rater (`pipeline/rater.py`) scores each paper on 7 dimensions and computes a weighted total. Stars are determined by Python thresholds — not by the model — so the arithmetic is always exact.

**Dimensions and weights:**

| Dimension | Weight | Score 1 | Score 2 | Score 3 |
|-----------|--------|---------|---------|---------|
| Pedigree | 30% | Unknown authors + unknown institution | Respected university or active researchers | Famous ML author or tier-1 lab (DeepMind, OpenAI, Meta AI, Nvidia, Apple ML, ByteDance AI, Microsoft Research) |
| Novelty | 20% | Incremental | Meaningful new idea | Paradigm shift |
| Breadth | 15% | Narrow task | Advances one subfield | Foundational / cross-field |
| Hype | 10% | Niche academic | Broader ML community | Likely viral |
| Code/demo | 5% | None | Mentioned, not live | Full release + live demo |
| Timing | 5% | Follow-up paper | Among first few | First to demonstrate capability |
| **Topic relevance** | **15%** | Pure LLM/NLP/agents | Image gen / multimodal | **World models / video gen / 3D** |

**Star thresholds** (total is a 0–1 weighted sum of `(score − 1) / 2`):

```
total > 0.65  →  ⭐⭐⭐
total ≥ 0.55  →  ⭐⭐
total < 0.55  →  ⭐
```

**To adapt the rater to your interests**, change the **Topic relevance** column in `RATING_PROMPT` to reflect what you care about most, and adjust weights to taste. For example, if you care more about robotics than video generation:

```
Topic relevance  15%   Score 1: pure LLM/NLP   Score 2: video/image gen   Score 3: robotics/embodied AI
```

### Number of papers per week

Change `MAX_WEEKLY = 5` at the top of `run_digest.py`.

### Scheduling

Run the script on a schedule using cron, launchd, or any task scheduler. A twice-daily cadence (6am/6pm) works well:

```
# crontab -e
0 6,18 * * * cd /path/to/AIDailyDigest && /path/to/conda/envs/ai-daily-digest-env/bin/python run_digest.py >> logs/digest.log 2>&1
```

---

## Project structure

```
AIDailyDigest/
├── run_digest.py          # Main pipeline orchestrator
├── sources/
│   ├── arxiv_source.py    # Fetches papers from arxiv cs.CV/LG/AI
│   └── affiliations.py    # Semantic Scholar + PDF fallback for author affiliations
├── pipeline/
│   ├── dedup.py           # Deduplication and abstract fetching
│   ├── filter.py          # Novelty filter (claude-haiku-4-5)
│   ├── formatter.py       # Paper card writer (claude-sonnet-4-6)
│   └── rater.py           # Impact rater — scores dimensions, Python computes stars
├── web/
│   ├── generate.py        # Builds self-contained index.html from CSS + JS + data
│   ├── app.js             # Sidebar and card rendering (vanilla JS)
│   └── style.css          # Styles
├── data/
│   └── digests.json       # Persistent store — keyed by ISO week (YYYY-Www)
├── .github/workflows/
│   └── pages.yml          # Deploys web/ to GitHub Pages on push
├── .env.example
└── requirements.txt
```

---

## Cost

Approximate API cost per run (100 arxiv papers fetched, ~10 pass the filter):

| Step | Model | Est. cost |
|------|-------|-----------|
| Novelty filter (100 papers) | claude-haiku-4-5 | ~$0.01 |
| Rating (10 papers) | claude-haiku-4-5 | ~$0.01 |
| Formatting (≤5 new papers) | claude-sonnet-4-6 | ~$0.03 |
| **Total** | | **~$0.05/run** |

At twice daily: ~$3/month.
