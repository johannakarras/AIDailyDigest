import json
import time

RATING_PROMPT = """You are assessing the impact and importance of a research paper for someone
tracking frontier ML research — with primary interest in world models and video generation,
secondary interest in image generation and multimodal systems, and lower interest in pure LLM /
NLP / agent papers.

Paper title: {title}
Authors: {authors}
Affiliations: {affiliations}
Abstract: {abstract}
Novelty reason (why it passed the novelty filter): {filter_reason}

Score the paper 1–3 on each dimension below.

─────────────────────────────────────────────────────────────────────────────
DIMENSION               WEIGHT   SCORE 1          SCORE 2          SCORE 3
─────────────────────────────────────────────────────────────────────────────
Pedigree                  30 %   Unknown authors  Active           Well-known
(author reputation              AND unknown /    researchers      author(s) in ML
 + institutional                small            OR a respected   (Yann LeCun,
 prestige combined)             institution      university       Fei-Fei Li,
                                                 (MIT, Stanford,  Jitendra Malik,
                                                 Berkeley, CMU,   Gordon Wetzstein,
                                                 UW, NYU,         Angjoo Kanazawa,
                                                 Princeton,       Pieter Abbeel…)
                                                 Oxford, ETH,     AND / OR a
                                                 Tsinghua, etc.)  tier-1 industry
                                                 OR mid-tier      lab: Google
                                                 industry lab     DeepMind, OpenAI,
                                                                  Meta AI Research,
                                                                  Nvidia Research,
                                                                  Apple ML,
                                                                  ByteDance AI,
                                                                  Microsoft Research

Novelty & insight         20 %   Incremental —    Meaningful new   Paradigm-shift
                                 passes the bar   idea or          or highly
                                 but expected     capability       surprising
                                                                   finding that
                                                                   opens a new
                                                                   research direction

Breadth of impact         15 %   Narrow task      Advances one     Foundational —
                                 improvement      subfield (e.g.   enables or
                                                  video gen,       affects many
                                                  3D recon)        downstream uses
                                                                   or subfields

Social-media hype         10 %   Niche academic   Broader ML       Likely to trend:
                                 interest only    community        flashy demo,
                                                  would notice     AI media picks
                                                                   up, goes viral

Code / demo release        5 %   No code or       Code or demo     Full released
                                 demo mentioned   mentioned but    code + live
                                                  not yet live     demo

First-mover / timing       5 %   Clear follow-up  Among the        First to
                                 or nth paper     first few on     demonstrate a
                                 on this topic    this topic       qualitatively
                                                                   new capability

Topic relevance           15 %   Pure LLM / NLP / Multimodal,      World models,
                                 speech / agents  image            video generation,
                                 / RAG / other    generation,      3D scene
                                 ML               vision-language  understanding,
                                                  understanding    neural rendering
─────────────────────────────────────────────────────────────────────────────

Scoring rules:
  • PEDIGREE RULE: If the paper comes from an institution explicitly listed in the Score 3 column
    (Google DeepMind, OpenAI, Meta AI Research, Nvidia Research, Apple ML, ByteDance AI,
    Microsoft Research) → pedigree MUST be 3.  A good university (MIT, Stanford, UW…) is
    pedigree=2, not 3, unless a famous named author (listed above) co-authored.
  • NOVELTY RULE: Passing the novelty filter sets the bar for novelty=2.  Novelty=3 requires a
    true paradigm-shift — an entirely new capability or finding that opens a new research
    direction.  Most filtered papers are novelty=2.

Worked examples (verify your arithmetic matches using total = Σ weight×(score−1)/2):
  • P2 N2 B2 H2 C1 T2 topic=1  → 0.30×0.5+0.20×0.5+0.15×0.5+0.10×0.5+0.05×0+0.05×0.5+0.15×0 = 0.40  → 1 star
  • P2 N2 B2 H2 C1 T2 topic=3  → same + 0.15×1.0 = 0.55  → 2 stars ★
  • P3 N2 B2 H2 C1 T2 topic=1  → 0.30×1.0+0.20×0.5+0.15×0.5+0.10×0.5+0.05×0+0.05×0.5+0.15×0 = 0.55  → 2 stars ★
  • P3 N2 B2 H2 C1 T2 topic=3  → 0.55 + 0.15×1.0 = 0.70  → 3 stars ★
  • P1 N2 B2 H2 C1 T2 topic=3  → 0.20×0.5+0.15×0.5+0.10×0.5+0.05×0+0.05×0.5+0.15×1.0 = 0.40  → 1 star

  total > 0.65  →  3 stars
  total < 0.55  →  1 star
  otherwise     →  2 stars

Respond with JSON only — output each dimension score, then a one-sentence rationale:
{{"pedigree": 1|2|3, "novelty": 1|2|3, "breadth": 1|2|3, "hype": 1|2|3, "code": 1|2|3, "timing": 1|2|3, "topic": 1|2|3, "rationale": "..."}}"""

_WEIGHTS = {
    "pedigree": 0.30,
    "novelty":  0.20,
    "breadth":  0.15,
    "hype":     0.10,
    "code":     0.05,
    "timing":   0.05,
    "topic":    0.15,
}


def _scores_to_stars(scores: dict) -> tuple[int, float]:
    total = sum(_WEIGHTS[k] * (scores[k] - 1) / 2 for k in _WEIGHTS)
    if total > 0.65:
        stars = 3
    elif total < 0.55:
        stars = 1
    else:
        stars = 2
    return stars, round(total, 3)


def rate_papers(papers: list[dict], client) -> list[dict]:
    """Add 'stars', 'rating_total', and 'rating_rationale' to each paper in-place."""
    for paper in papers:
        stars, total, rationale = _rate_paper(paper, client)
        paper["stars"] = stars
        paper["rating_total"] = total
        paper["rating_rationale"] = rationale
    return papers


def _rate_paper(paper: dict, client) -> tuple[int, float, str]:
    import anthropic

    prompt = RATING_PROMPT.format(
        title=paper.get("title", ""),
        authors=", ".join(paper.get("authors") or []),
        affiliations=", ".join(paper.get("affiliations") or []),
        abstract=paper.get("abstract", ""),
        filter_reason=paper.get("filter_reason", ""),
    )

    for attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            brace = text.find("{")
            end = text.rfind("}") + 1
            if brace != -1 and end > brace:
                text = text[brace:end]
            result = json.loads(text)

            scores = {k: max(1, min(3, int(result.get(k, 2)))) for k in _WEIGHTS}
            stars, total = _scores_to_stars(scores)
            rationale = str(result.get("rationale", ""))

            _abbr = {"pedigree": "P", "novelty": "N", "breadth": "B", "hype": "H", "code": "C", "timing": "M", "topic": "R"}
            dims = " ".join(f"{_abbr[k]}{scores[k]}" for k in _WEIGHTS)
            print(f"[rater] {paper['id']}: {'⭐' * stars} (total={total}) [{dims}] — {rationale}")
            return stars, total, rationale
        except anthropic.RateLimitError:
            if attempt == 0:
                print("[rater] Rate limited, waiting 60s...")
                time.sleep(60)
            else:
                return 2, 0.5, ""
        except Exception as e:
            print(f"[rater] Failed for {paper['id']}: {e}")
            return 2, 0.5, ""

    return 2, 0.5, ""
