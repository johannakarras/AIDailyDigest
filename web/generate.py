import json
import os
import sys


def generate_html(digests: dict, output_path: str = "web/index.html") -> None:
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    js_path = os.path.join(os.path.dirname(__file__), "app.js")

    with open(css_path) as f:
        css = f.read()
    with open(js_path) as f:
        js = f.read()

    serialized = json.dumps(digests, ensure_ascii=False, indent=2)
    serialized = serialized.replace("</script>", "<\\/script>")

    html = _build_html(css, js, serialized)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def _build_html(css: str, js: str, digests_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Johanna's AI Daily Digest</title>
  <style>
{css}
  </style>
</head>
<body>
  <nav id="sidebar">
    <h2>Archive</h2>
  </nav>
  <main id="content">
    <div id="content-header">
      <h1>Johanna's AI Daily Digest</h1>
      <p id="site-description">An AI agent that curates the most relevant recent papers in generative AI — image &amp; video synthesis, world models, and LLMs — ranked and filtered to match my research interests. Feel free to fork the <a href="https://github.com" target="_blank" rel="noopener noreferrer">codebase</a> and build your own agentic paper curator.</p>
      <p id="date-heading"></p>
    </div>
    <div id="cards-container"></div>
  </main>
  <script>
const DIGESTS = {digests_json};
{js}
  </script>
</body>
</html>"""


if __name__ == "__main__":
    digests_path = os.path.join(os.path.dirname(__file__), "..", "data", "digests.json")
    if not os.path.exists(digests_path):
        print(f"No digests.json found at {digests_path}")
        sys.exit(1)

    with open(digests_path) as f:
        digests = json.load(f)

    out = os.path.join(os.path.dirname(__file__), "index.html")
    generate_html(digests, output_path=out)
    print(f"Generated {out}")
