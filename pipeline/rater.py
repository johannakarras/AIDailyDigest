import json
import os as _os
import time

_SKILL_PATH = _os.path.join(_os.path.dirname(__file__), "..", "skills", "paper_rater.md")
with open(_SKILL_PATH) as _f:
    RATING_PROMPT = _f.read()

_OVERRIDES_PATH = _os.path.join(_os.path.dirname(__file__), "..", "data", "rating_overrides.json")


def _load_examples_section() -> str:
    if not _os.path.exists(_OVERRIDES_PATH):
        return ""
    with open(_OVERRIDES_PATH) as f:
        overrides = json.load(f)
    if not overrides:
        return ""
    lines = [
        "Past manual corrections — calibrate against these if you are unsure:",
        "",
    ]
    for o in overrides:
        stars_before = "★" * o["auto_stars"] + "☆" * (3 - o["auto_stars"])
        stars_after  = "★" * o["manual_stars"] + "☆" * (3 - o["manual_stars"])
        affs = ", ".join(o.get("affiliations") or [])
        lines.append(f'• "{o["title"]}"' + (f" ({affs})" if affs else ""))
        lines.append(f'  Auto-rated {stars_before} → manually corrected to {stars_after}')
        lines.append(f'  Lesson: {o["reason"]}')
        lines.append("")
    return "\n".join(lines)

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
        examples_section=_load_examples_section(),
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
