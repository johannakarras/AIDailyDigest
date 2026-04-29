import re


def normalize_id(arxiv_id: str) -> str:
    cleaned = arxiv_id.lower().replace("arxiv:", "").strip()
    return re.sub(r"v\d+$", "", cleaned)


def load_seen_ids(digests: dict) -> set[str]:
    seen = set()
    for papers in digests.values():
        for paper in papers:
            if paper.get("id"):
                seen.add(normalize_id(paper["id"]))
    return seen


def deduplicate_candidates(candidates: list[dict], seen_ids: set[str]) -> list[dict]:
    arxiv_first = sorted(candidates, key=lambda p: 0 if p.get("source") == "arxiv" else 1)

    unique: dict[str, dict] = {}
    for paper in arxiv_first:
        if not paper.get("id"):
            continue
        nid = normalize_id(paper["id"])
        if nid in seen_ids:
            continue
        if nid not in unique:
            unique[nid] = paper

    return list(unique.values())


def fetch_missing_abstracts(papers: list[dict]) -> list[dict]:
    import arxiv as arxiv_lib

    stubs = [p for p in papers if not p.get("abstract")]
    if not stubs:
        return papers

    stub_ids = [p["id"] for p in stubs]
    fetched: dict[str, dict] = {}

    batch_size = 50
    for i in range(0, len(stub_ids), batch_size):
        batch = stub_ids[i : i + batch_size]
        try:
            client = arxiv_lib.Client()
            search = arxiv_lib.Search(id_list=batch)
            for result in client.results(search):
                raw_id = result.get_short_id()
                nid = re.sub(r"v\d+$", "", raw_id)
                fetched[nid] = {
                    "title": result.title.strip(),
                    "abstract": result.summary.strip(),
                    "url": f"https://arxiv.org/abs/{nid}",
                    "submitted_date": result.published.strftime("%Y-%m-%d"),
                    "authors": [a.name for a in result.authors[:5]],
                }
        except Exception as e:
            print(f"[dedup] Failed to fetch abstracts for batch {i}: {e}")

    result_papers = []
    for paper in papers:
        if paper.get("abstract"):
            result_papers.append(paper)
            continue

        nid = normalize_id(paper["id"])
        if nid in fetched:
            paper.update(fetched[nid])
            result_papers.append(paper)
        else:
            print(f"[dedup] Could not fetch abstract for {paper['id']}, dropping")

    return result_papers
