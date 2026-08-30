from __future__ import annotations

import re
from typing import List


def parse_front_matter(markdown_text: str) -> tuple[dict[str, str], str]:
    """Extract YAML-like front matter and the remainder of the markdown."""
    if not markdown_text.lstrip().startswith("---"):
        return {}, markdown_text

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", markdown_text, re.DOTALL)
    if not match:
        return {}, markdown_text

    front_matter_raw, body = match.groups()
    data: dict[str, str] = {}
    for line in front_matter_raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"\'')
    return data, body


def split_slides(markdown_text: str) -> List[str]:
    """Return a slide list where the H1 becomes the title page and each H2 is one slide."""
    front_matter, body = parse_front_matter(markdown_text)
    body = body.strip()
    if not body:
        return []

    lines = body.splitlines()
    slides: List[str] = []
    current: List[str] = []
    current_heading: str | None = None

    def flush_current() -> None:
        nonlocal current
        if current:
            slides.append("\n".join(current).strip())
            current = []

    title_match = re.match(r"^#\s+(.+)$", body, re.MULTILINE)
    if title_match:
        title_text = title_match.group(1).strip()
        title_lines = [f"# {title_text}", ""]
        meta_html = []
        if front_matter.get("author"):
            meta_html.append(f"<div><strong>Author:</strong> {front_matter['author']}</div>")
        if front_matter.get("date"):
            meta_html.append(f"<div><strong>Date:</strong> {front_matter['date']}</div>")
        if meta_html:
            title_lines.append(f"<div class=\"title-meta\">{''.join(meta_html)}</div>")
        slides.append("\n".join(title_lines))

        body_after_title = re.sub(r"^#\s+.+\n*", "", body, count=1)
        lines = body_after_title.splitlines()
    elif front_matter.get("title"):
        slides.append(f"# {front_matter['title']}")

    for line in lines:
        if re.match(r"^##\s+", line):
            flush_current()
            current_heading = line
            current = [line]
            continue
        if current:
            current.append(line)

    flush_current()

    return [slide for slide in slides if slide.strip()]


def render_html(markdown_text: str) -> str:
    """Return a minimal HTML document for a slide deck."""
    slides = split_slides(markdown_text)
    html_slides = "\n".join(
        f"<section class=\"slide\">{slide}</section>" for slide in slides
    )
    return f"""<!doctype html>
<html lang=\"ja\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Markdown LT</title>
    <style>
      body {{
        margin: 0;
        font-family: sans-serif;
        background: #111827;
        color: #f9fafb;
      }}
      .slide {{
        min-height: 100vh;
        box-sizing: border-box;
        padding: 3rem;
        border-bottom: 1px solid rgba(255,255,255,0.2);
      }}
      .slide:first-child {{
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
      }}
      h1, h2, h3 {{ margin-top: 0; }}
      code {{ background: rgba(255,255,255,0.08); padding: 0.1rem 0.3rem; border-radius: 0.25rem; font-size: 0.74rem; }}
      pre {{ background: #020817; color: #e2e8f0; padding: 0.6rem 0.75rem 0.45rem; overflow: auto; border-radius: 0.5rem; border: 1px solid rgba(148,163,184,0.2); box-sizing: border-box; font-size: 0.74rem; line-height: 1.45; }}
      blockquote {{ border-left: 4px solid #60a5fa; padding-left: 1rem; color: #dbeafe; }}
      ul, ol {{ padding-left: 1.5rem; }}
    </style>
  </head>
  <body>
    {html_slides}
  </body>
</html>
"""
