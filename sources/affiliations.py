import base64
import io
import json
import time

import requests

S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
BATCH_SIZE = 100

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIDailyDigest/1.0)"}

_TEXT_PROMPT = """The following text is from the first page of an academic paper.
Extract all institutional affiliations (universities, companies, research labs).

Text:
{text}

Return a JSON array of strings e.g. ["MIT", "Google DeepMind", "Stanford University"].
Include only institution names. Exclude email addresses, URLs, and superscript numbers.
Return [] if none found. Respond with only valid JSON."""

_VISION_PROMPT = """This is the header of an academic paper (title, authors, and affiliations).
Extract every institutional affiliation visible — universities, companies, and research labs
(e.g. "ByteDance", "OpenAI", "Google", "Alibaba", "MIT", "Stanford University").

Return a JSON array of strings, e.g. ["Google DeepMind", "MIT", "Peking University"].
Include only institution names. Exclude author names, email addresses, and URLs.
Return [] if no affiliations are visible. Respond with only valid JSON."""


def fetch_affiliations(arxiv_ids: list[str]) -> dict[str, list[str]]:
    """Batch-fetch affiliations from Semantic Scholar (fast; has a few-day indexing lag)."""
    if not arxiv_ids:
        return {}

    result: dict[str, list[str]] = {}
    params = {"fields": "externalIds,authors.affiliations"}

    for i in range(0, len(arxiv_ids), BATCH_SIZE):
        batch = arxiv_ids[i : i + BATCH_SIZE]
        payload = {"ids": [f"arXiv:{aid}" for aid in batch]}
        try:
            resp = requests.post(S2_BATCH_URL, params=params, json=payload, timeout=30)
            resp.raise_for_status()
            for paper in resp.json():
                if not paper:
                    continue
                ext = paper.get("externalIds") or {}
                arxiv_id = ext.get("ArXiv", "")
                if not arxiv_id:
                    continue
                seen: set[str] = set()
                affs: list[str] = []
                for author in paper.get("authors") or []:
                    for aff in author.get("affiliations") or []:
                        aff = aff.strip()
                        if aff and aff not in seen:
                            seen.add(aff)
                            affs.append(aff)
                result[arxiv_id] = affs
        except Exception as e:
            print(f"[affiliations] S2 batch {i} failed: {e}")

        if i + BATCH_SIZE < len(arxiv_ids):
            time.sleep(1)

    found = sum(1 for v in result.values() if v)
    print(f"[affiliations] S2: found affiliations for {found}/{len(arxiv_ids)} papers")
    return result


def fetch_affiliations_from_pdf(arxiv_id: str, client) -> list[str]:
    """Extract affiliations from PDF page 1.

    Strategy:
    1. Download the PDF.
    2. Extract text from page 1 and ask an LLM to parse affiliations.
    3. If the text pass returns nothing, rasterize the top third of page 1
       as an image and ask a vision model to read the affiliations directly.
    """
    pdf_bytes = _download_pdf(arxiv_id)
    if not pdf_bytes:
        return []

    # --- Pass 1: text extraction ---
    first_page_text = _extract_first_page_text(pdf_bytes)
    if first_page_text:
        cutoff = first_page_text.lower().find("abstract")
        excerpt = first_page_text[:cutoff] if cutoff > 0 else first_page_text[:800]
        affs = _parse_with_llm(excerpt, client, _TEXT_PROMPT)
        if affs:
            print(f"[affiliations] PDF text: {arxiv_id} -> {affs}")
            return affs

    # --- Pass 2: vision on the header image ---
    print(f"[affiliations] text pass empty for {arxiv_id}, trying vision...")
    header_image = _rasterize_header(pdf_bytes)
    if not header_image:
        return []

    affs = _parse_with_vision(header_image, client)
    if affs:
        print(f"[affiliations] PDF vision: {arxiv_id} -> {affs}")
    return affs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_pdf(arxiv_id: str) -> bytes | None:
    try:
        resp = requests.get(
            f"https://arxiv.org/pdf/{arxiv_id}",
            headers=_HEADERS,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"[affiliations] PDF download failed for {arxiv_id}: {e}")
        return None


def _extract_first_page_text(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return pdf.pages[0].extract_text() or ""
    except Exception as e:
        print(f"[affiliations] pdfplumber failed: {e}")
        return ""


def _rasterize_header(pdf_bytes: bytes) -> bytes | None:
    """Render the top third of PDF page 1 as a PNG at ~144 DPI."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        # Crop to the top third of the page where the header lives
        clip = fitz.Rect(0, 0, page.rect.width, page.rect.height / 3)
        mat = fitz.Matrix(2.0, 2.0)  # 2× zoom ≈ 144 DPI
        pix = page.get_pixmap(matrix=mat, clip=clip)
        return pix.tobytes("png")
    except Exception as e:
        print(f"[affiliations] rasterization failed: {e}")
        return None


def _parse_with_llm(text: str, client, prompt_template: str) -> list[str]:
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt_template.format(text=text)}],
        )
        return _parse_json_list(resp.content[0].text)
    except Exception as e:
        print(f"[affiliations] LLM call failed: {e}")
        return []


def _parse_with_vision(image_bytes: bytes, client) -> list[str]:
    img_b64 = base64.standard_b64encode(image_bytes).decode()
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }],
        )
        return _parse_json_list(resp.content[0].text)
    except Exception as e:
        print(f"[affiliations] vision call failed: {e}")
        return []


def _parse_json_list(text: str) -> list[str]:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [str(s).strip() for s in result if s]
    except json.JSONDecodeError:
        pass
    return []
