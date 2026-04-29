import json
import time

OUTPUT_PROMPT = """Given this paper, produce a JSON object with exactly these fields:
- "description": One sentence starting with a verb (e.g. "Trains...", "Introduces...") describing what the model/method does
- "contribution": 2-3 sentences on what is specifically novel — the insight or contribution that distinguishes this from prior work
- "limitations": 1-2 sentences on limitations or assumptions this paper makes
- "links": array of {{"label": string, "url": string}} for any project pages, demo pages, or code repositories explicitly mentioned in the abstract (e.g. "Project Page", "GitHub", "Demo"). Return [] if none are mentioned.

Do not mention the dataset unless it is the contribution. Do not summarize the experiments.
Focus on the idea, not the results.

Paper title: {title}
Abstract: {abstract}

Respond with only valid JSON."""


def format_papers(papers: list[dict], client, max_papers: int = 5) -> list[dict]:
    """Format papers in-place (adds description/contribution/limitations/links).
    Returns the subset that were successfully formatted."""
    formatted = []
    for paper in papers[:max_papers]:
        if _format_paper(paper, client):
            formatted.append(paper)
    return formatted


def _format_paper(paper: dict, client) -> bool:
    """Add description/contribution/limitations/links to paper dict in-place.
    Returns True on success, False on failure."""
    import anthropic

    prompt = OUTPUT_PROMPT.format(
        title=paper.get("title", ""),
        abstract=paper.get("abstract", ""),
    )

    for attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            fields = json.loads(text)

            for key in ("description", "contribution", "limitations"):
                val = fields.get(key, "")
                if isinstance(val, list):
                    fields[key] = " ".join(str(v) for v in val)
                else:
                    fields[key] = str(val)

            if not all(fields.get(k) for k in ("description", "contribution", "limitations")):
                print(f"[formatter] Missing fields for {paper['id']}, skipping")
                return False

            links = fields.get("links", [])
            if not isinstance(links, list):
                links = []

            paper["description"] = fields["description"]
            paper["contribution"] = fields["contribution"]
            paper["limitations"] = fields["limitations"]
            paper["links"] = links
            if "date" not in paper:
                paper["date"] = paper.get("submitted_date", "")
            return True
        except anthropic.RateLimitError:
            if attempt == 0:
                print("[formatter] Rate limited, waiting 60s...")
                time.sleep(60)
            else:
                print(f"[formatter] Rate limit persists for {paper['id']}, skipping")
                return False
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[formatter] Parse error for {paper['id']}: {e}, skipping")
            return False
        except Exception as e:
            print(f"[formatter] API error for {paper['id']}: {e}, skipping")
            return False

    return False
