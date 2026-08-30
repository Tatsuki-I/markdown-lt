from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from markdown_it import MarkdownIt
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from .slides import parse_front_matter, split_slides
from .themes import get_theme


def resolve_source_path(source: str | Path) -> Path:
    path = Path(source)
    if path.is_absolute():
        return path
    project_root = Path(__file__).resolve().parents[2]
    return project_root / path


def load_markdown(source: str | Path) -> str:
    path = resolve_source_path(source)
    return path.read_text(encoding="utf-8")


def list_slide_folders(base_dir: str | Path = "slides") -> list[Path]:
    root = resolve_source_path(base_dir)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def resolve_slide_file_for_folder(folder_name: str, base_dir: str | Path = "slides") -> Path | None:
    root = resolve_source_path(base_dir)
    folder = root / folder_name
    if not folder.is_dir():
        return None

    preferred_names = ["index.md", "deck.md", "slide.md", "sample-slide.md", "README.md"]
    for name in preferred_names:
        path = folder / name
        if path.exists() and path.is_file():
            return path

    markdown_files = sorted(folder.glob("*.md"))
    if markdown_files:
        return markdown_files[0]

    text_files = sorted(folder.glob("*.text"))
    if text_files:
        return text_files[0]

    return None


def extract_deck_metadata(folder: Path, base_dir: str | Path = "slides") -> dict[str, str]:
    root = resolve_source_path(base_dir)
    deck_file = resolve_slide_file_for_folder(folder.name, root)
    if deck_file is None:
        return {
            "folder": folder.name,
            "title": folder.name,
            "author": "",
            "date": "",
        }

    try:
        text = deck_file.read_text(encoding="utf-8")
    except OSError:
        return {
            "folder": folder.name,
            "title": folder.name,
            "author": "",
            "date": "",
        }

    front_matter, _ = parse_front_matter(text)
    title = front_matter.get("title") or folder.name
    subtitle = front_matter.get("subtitle") or ""
    author = front_matter.get("author") or ""
    date = front_matter.get("date") or ""
    return {
        "folder": folder.name,
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "date": date,
    }


def parse_timer_env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    return value if value > 0 else default


def get_timer_config() -> dict[str, dict[str, int]]:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    easy_seconds = parse_timer_env_int("TIMER_EASY_SECONDS", 300)
    easy_alert_seconds = parse_timer_env_int("TIMER_EASY_ALERT_SECONDS", 60)
    hard_seconds = parse_timer_env_int("TIMER_HARD_SECONDS", 180)
    hard_alert_seconds = parse_timer_env_int("TIMER_HARD_ALERT_SECONDS", 30)

    return {
        "easy": {
            "seconds": easy_seconds,
            "alertSeconds": easy_alert_seconds,
        },
        "hard": {
            "seconds": hard_seconds,
            "alertSeconds": hard_alert_seconds,
        },
    }


def render_slide_index_html(folders: list[Path]) -> str:
    env = get_template_environment()
    template = env.get_template("deck_index.html.j2")
    deck_cards = [extract_deck_metadata(folder, "slides") for folder in folders]
    return template.render(decks=deck_cards)


def get_template_environment() -> Environment:
    template_dir = Path(__file__).resolve().parents[2] / "templates"
    return Environment(loader=FileSystemLoader(str(template_dir)))


def render_markdown_fragment(fragment: str) -> str:
    """Convert Markdown while preserving Mermaid blocks and note admonitions before generic parsing."""
    normalized = fragment.replace("::::note", ":::note")

    def convert_ruby(match: re.Match[str]) -> str:
        text, ruby = match.group(1), match.group(2)
        return f"<ruby>{text}<rt>{ruby}</rt></ruby>"

    def convert_strikethrough(match: re.Match[str]) -> str:
        text = match.group(1)
        return f"<del>{text}</del>"

    def render_common_markdown(text: str) -> str:
        return MarkdownIt("commonmark").enable("strikethrough").render(text)

    def normalize_nested_ordered_lists(text: str) -> str:
        lines = text.splitlines()
        result: list[str] = []
        previous_nonempty = ""
        for line in lines:
            stripped = line.strip()
            if re.match(r"^\s*\d+\.\s+", line):
                indent = len(line) - len(line.lstrip(" "))
                if indent == 2 and previous_nonempty and re.match(r"^\d+\.\s+", previous_nonempty):
                    line = " " * 3 + line.lstrip()
            result.append(line)
            if stripped:
                previous_nonempty = stripped
        return "\n".join(result)

    normalized = re.sub(r"\{([^{}]+)\|([^{}]+)\}", convert_ruby, normalized)
    normalized = re.sub(r"~~([^~\n][^~]*?)~~", convert_strikethrough, normalized)
    normalized = normalize_nested_ordered_lists(normalized)

    def convert_note(match: re.Match[str]) -> str:
        note_type = (match.group(1) or "info").lower()
        label_map = {
            "info": "Info",
            "warn": "Warning",
            "alert": "Alert",
        }
        label = label_map.get(note_type, note_type.title())
        body = match.group(2).strip()
        body_html = render_common_markdown(body)
        return (
            f'<div class="note note-{note_type}">'
            f'<div class="note-header">{label}</div>'
            f'<div class="note-body">{body_html}</div>'
            '</div>'
        )

    normalized = re.sub(
        r"(?s):::note\s*([A-Za-z0-9_-]+)?\s*\n(.*?)\n:::",
        convert_note,
        normalized,
    )
    normalized = re.sub(
        r"```mermaid\s*\n(.*?)\n```",
        lambda m: f'<pre class="mermaid">{m.group(1).strip()}</pre>',
        normalized,
        flags=re.DOTALL,
    )
    converted = render_common_markdown(normalized)
    converted = re.sub(
        r'<pre><code class="language-([a-zA-Z0-9_+-]+)">',
        lambda m: f'<pre class="line-numbers"><code class="language-{m.group(1)}">',
        converted,
    )
    return converted


def render_slide_html(slide: str) -> str:
    """Render a slide with header/body/footer structure and footer notes."""
    normalized = slide.strip()
    footer_sections: list[str] = []

    note_match = re.search(r"(?s)(\n*:::note\s*[A-Za-z0-9_-]*\s*\n.*?\n:::\s*)$", normalized)
    if note_match:
        footer_sections.append(render_markdown_fragment(note_match.group(1).strip()))
        normalized = normalized[: note_match.start()].rstrip()

    quote_match = re.search(r"(?ms)^(?:>\s.*(?:\n>.*)*)\s*$", normalized)
    if quote_match:
        footer_sections.append(render_markdown_fragment(quote_match.group(0).strip()))
        normalized = normalized[: quote_match.start()].rstrip()

    header_html = ""
    body_source = normalized
    if normalized.startswith("## "):
        lines = normalized.splitlines()
        header_line = lines[0].strip()
        remainder = "\n".join(lines[1:]).strip()
        if header_line:
            header_html = render_markdown_fragment(header_line)
            body_source = remainder

    side_tag = r"(?:Left|Center|Centre|Right)"
    if re.search(rf"^###\s+{side_tag}(?:\s+(?:Top|Bottom))?\s*$", body_source, flags=re.MULTILINE):
        parts = re.split(rf"(?m)^###\s+((?:{side_tag})(?:\s+(?:Top|Bottom))?)\s*$", body_source)
        left = []
        center = []
        right = []
        right_top = []
        right_bottom = []
        center_top = []
        center_bottom = []
        current_name = None

        for chunk in parts:
            text = chunk.strip()
            if not text:
                continue

            match = re.fullmatch(r"(Left|Center|Centre|Right)(?:\s+(Top|Bottom))?", text)
            if match:
                value = text.replace("Centre", "Center")
                if value in {"Left", "Center", "Right"}:
                    current_name = value
                else:
                    current_name = value
                continue

            if current_name == "Left":
                left.append(text)
            elif current_name == "Center":
                center.append(text)
            elif current_name == "Right":
                right.append(text)
            elif current_name == "Right Top":
                right_top.append(text)
            elif current_name == "Right Bottom":
                right_bottom.append(text)
            elif current_name == "Center Top":
                center_top.append(text)
            elif current_name == "Center Bottom":
                center_bottom.append(text)

        if left or center or right or right_top or right_bottom or center_top or center_bottom:
            left_html = render_markdown_fragment("\n".join(left)) if left else ""
            center_html = render_markdown_fragment("\n".join(center)) if center else ""
            right_html = render_markdown_fragment("\n".join(right)) if right else ""
            right_top_html = render_markdown_fragment("\n".join(right_top)) if right_top else ""
            right_bottom_html = render_markdown_fragment("\n".join(right_bottom)) if right_bottom else ""
            center_top_html = render_markdown_fragment("\n".join(center_top)) if center_top else ""
            center_bottom_html = render_markdown_fragment("\n".join(center_bottom)) if center_bottom else ""

            right_stack_mode = bool(left and right_top and right_bottom)
            center_stack_mode = bool(left and center_top and center_bottom and right)

            if left and center and right:
                body_html = (
                    '<div class="three-col">'
                    f'<div class="left-column">{left_html}</div>'
                    f'<div class="center-column">{center_html}</div>'
                    f'<div class="right-column">{right_html}</div>'
                    '</div>'
                )
            elif center_stack_mode:
                body_html = (
                    '<div class="three-col">'
                    f'<div class="left-column">{left_html}</div>'
                    '<div class="center-stack">'
                    f'<div class="top-column">{center_top_html}</div>'
                    f'<div class="bottom-column">{center_bottom_html}</div>'
                    '</div>'
                    f'<div class="right-column">{right_html}</div>'
                    '</div>'
                )
            elif right_stack_mode:
                body_html = (
                    '<div class="left-right-vertical">'
                    f'<div class="left-column">{left_html}</div>'
                    f'<div class="right-stack">'
                    f'<div class="top-column">{right_top_html}</div>'
                    f'<div class="bottom-column">{right_bottom_html}</div>'
                    '</div>'
                    '</div>'
                )
            else:
                body_html = (
                    '<div class="two-col">'
                    f'<div class="left-column">{left_html}</div>'
                    f'<div class="right-column">{right_html}</div>'
                    '</div>'
                )
        else:
            body_html = render_markdown_fragment(body_source)
    else:
        body_html = render_markdown_fragment(body_source)

    footer_html = ""
    if footer_sections:
        footer_html = (
            '<div class="slide-footer">'
            '<div class="footer-note">'
            + "".join(footer_sections)
            + '</div>'
            '</div>'
        )

    template = get_template_environment().get_template("slide_shell.html.j2")
    return template.render(
        header_html=header_html,
        body_html=body_html,
        footer_html=footer_html,
    )


def build_slide_html(markdown_text: str, theme_name: str = "default") -> str:
    slides = split_slides(markdown_text)

    front_matter, body = parse_front_matter(markdown_text)
    title = front_matter.get("title") or "Markdown LT"
    author = front_matter.get("author")
    date = front_matter.get("date")
    theme = get_theme(theme_name)

    subtitle_text = front_matter.get("subtitle", "")
    if not subtitle_text and body.strip():
        title_match = re.match(r"^#\s+.+?\n+(.*?)(?=\n##\s+|\Z)", body.strip(), flags=re.DOTALL)
        if title_match:
            candidate = title_match.group(1).strip()
            candidate = re.sub(r"<[^>]+>", "", candidate)
            if candidate and not candidate.startswith("#") and not candidate.startswith("###"):
                subtitle_text = candidate.strip()

    rendered_slides: list[str] = []
    for index, slide in enumerate(slides):
        if index == 0 and slide.lstrip().startswith("# "):
            meta_parts: list[str] = []
            if author:
                meta_parts.append(
                    '<div class="meta-row">'
                    '<span class="meta-label">Author:</span>'
                    f'<span class="meta-value">{author}</span>'
                    '</div>'
                )
            if date:
                meta_parts.append(
                    '<div class="meta-row">'
                    '<span class="meta-label">Date:</span>'
                    f'<span class="meta-value">{date}</span>'
                    '</div>'
                )

            subtitle_html = subtitle_text
            meta_html = ''.join(meta_parts)
            template = get_template_environment().get_template("title_slide.html.j2")
            rendered_slides.append(
                template.render(
                    title=title,
                    subtitle_html=subtitle_html,
                    meta_html=meta_html,
                )
            )
            continue
        rendered_slides.append(render_slide_html(slide))

    env = get_template_environment()
    template = env.get_template("slide_deck.html.j2")
    return template.render(
        title=title,
        author=author,
        date=date,
        slides=rendered_slides,
        theme=theme,
        timer_config=get_timer_config(),
    )


def create_app(source: str | Path = "slides", theme_name: str = "default") -> FastAPI:
    app = FastAPI(title="Markdown LT")
    source_path = resolve_source_path(source)
    static_dir = Path(__file__).resolve().parents[2] / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def index() -> HTMLResponse:
        if source_path.is_file():
            text = load_markdown(source_path)
            html = build_slide_html(text, theme_name=theme_name)
            return HTMLResponse(content=html)

        folders = list_slide_folders(source_path)
        return HTMLResponse(content=render_slide_index_html(folders))

    @app.get("/slides/{folder_name}")
    async def deck(folder_name: str) -> HTMLResponse:
        slide_file = resolve_slide_file_for_folder(folder_name, source_path)
        if slide_file is None:
            raise HTTPException(status_code=404, detail=f"No slide deck found for '{folder_name}'")
        text = load_markdown(slide_file)
        html = build_slide_html(text, theme_name=theme_name)
        return HTMLResponse(content=html)

    @app.get("/{folder_name}")
    async def deck_short(folder_name: str) -> HTMLResponse:
        return await deck(folder_name)

    return app


app = create_app()
