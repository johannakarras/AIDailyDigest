import re
import time
from datetime import datetime, timedelta, timezone

import arxiv


def fetch_arxiv_papers(days_back: int = 7, max_results: int = 100) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    query = "cat:cs.CV OR cat:cs.LG OR cat:cs.AI"

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    for attempt in range(3):
        try:
            papers: dict[str, dict] = {}
            for result in client.results(search):
                if result.published < cutoff:
                    break

                raw_id = result.get_short_id()
                normalized = re.sub(r"v\d+$", "", raw_id)

                if normalized in papers:
                    continue

                papers[normalized] = {
                    "id": normalized,
                    "title": result.title.strip(),
                    "abstract": result.summary.strip(),
                    "url": f"https://arxiv.org/abs/{normalized}",
                    "submitted_date": result.published.strftime("%Y-%m-%d"),
                    "authors": [a.name for a in result.authors[:5]],
                    "source": "arxiv",
                }

            return list(papers.values())

        except arxiv.HTTPError as e:
            if e.status == 429 and attempt < 2:
                wait = 300 * (attempt + 1)  # 5 min, then 10 min
                print(f"[arxiv] Rate limited (429). Retrying in {wait}s ({wait//60} min)...")
                time.sleep(wait)
            else:
                raise
