import json
import os as _os
import time

_SKILL_PATH = _os.path.join(_os.path.dirname(__file__), "..", "skills", "paper_evaluator.md")
with open(_SKILL_PATH) as _f:
    NOVELTY_PROMPT = _f.read()


def filter_for_novelty(papers: list[dict], client) -> tuple[list[dict], list[dict]]:
    passing = []
    rejected = []
    for paper in papers:
        result = _score_paper(paper, client)
        if result is not None:
            passing.append(result)
        else:
            rejected.append(paper)
    return passing, rejected


def _score_paper(paper: dict, client) -> dict | None:
    import anthropic

    prompt = NOVELTY_PROMPT.format(
        title=paper.get("title", ""),
        abstract=paper.get("abstract", ""),
    )

    for attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(text)
            passed = bool(result.get("pass"))
            reason = result.get("reason", "")
            status = "PASS" if passed else "REJECT"
            print(f"[filter] {paper['id']}: {status} — {reason}")
            paper["filter_reason"] = reason
            if passed:
                return paper
            return None
        except anthropic.RateLimitError:
            if attempt == 0:
                print("[filter] Rate limited, waiting 60s...")
                time.sleep(60)
            else:
                print(f"[filter] Rate limit persists for {paper['id']}, rejecting")
                return None
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"[filter] Parse error for {paper['id']}: {e}, rejecting")
            return None
        except Exception as e:
            print(f"[filter] API error for {paper['id']}: {e}, rejecting")
            return None

    return None
