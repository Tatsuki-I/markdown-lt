from pathlib import Path

from fastapi.testclient import TestClient

from markdown_lt.cli import resolve_default_source
from markdown_lt.server import create_app, render_markdown_fragment, render_slide_html
from markdown_lt.slides import split_slides
from markdown_lt.themes import get_theme


def test_split_slides_by_heading_and_front_matter():
    source = """---
title: "Deck title"
author: "Tatsuki"
---

# Deck title

## Intro

hello world

## Next

second page
"""

    slides = split_slides(source)

    assert len(slides) == 3
    assert slides[0].startswith("# Deck title")
    assert slides[1].startswith("## Intro")
    assert slides[2].startswith("## Next")


def test_default_theme_has_expected_tokens():
    theme = get_theme("default")

    assert theme["background"] == "#0f172a"
    assert theme["text"] == "#e2e8f0"
    assert theme["accent"] == "#38bdf8"


def test_render_slide_html_supports_left_right_columns():
    slide = """## Demo

### Left

- one
- two

### Right

- three
- four
"""

    html = render_slide_html(slide)

    assert "slide-header" in html
    assert "slide-body" in html
    assert "slide-footer" not in html
    assert "two-col" in html
    assert "left-column" in html
    assert "right-column" in html


def test_render_slide_html_supports_right_stack_top_and_bottom_only():
    slide = """## Demo

### Left

- left

### Right Top

- top

### Right Bottom

- bottom
"""

    html = render_slide_html(slide)

    assert "left-right-vertical" in html
    assert "right-stack" in html
    assert "top-column" in html
    assert "bottom-column" in html
    assert "left-stack" not in html


def test_render_slide_html_supports_center_stack_top_and_bottom_only():
    slide = """## Demo

### Left

- left

### Centre Top

- top

### Centre Bottom

- bottom

### Right

- right
"""

    html = render_slide_html(slide)

    assert "three-col" in html
    assert "center-stack" in html
    assert "top-column" in html
    assert "bottom-column" in html


def test_render_slide_html_keeps_h2_out_of_left_column_when_followed_by_split_sections():
    slide = """## hoge

### Left

1. 数字の
1. 箇条書きも
1. できます

### Right

左右分割もできますよ。
"""

    html = render_slide_html(slide)

    assert "<h2>hoge</h2>" in html
    assert html.index("<h2>hoge</h2>") < html.index("left-column")
    assert "<h2>hoge</h2>" not in html[html.index("left-column"):]


def test_render_slide_html_supports_mermaid_and_code_blocks():
    slide = """## Demo

```python
def hello():
    print("hello")
```

```mermaid
flowchart LR
A --> B
```
"""

    html = render_slide_html(slide)

    assert "language-python" in html
    assert "line-numbers" in html
    assert "class=\"mermaid\"" in html
    assert "flowchart LR" in html
    assert "def hello" in html


def test_render_markdown_fragment_supports_ruby_syntax():
    html = render_markdown_fragment("{寿限無|じゅげむ}")

    assert "<ruby>寿限無<rt>じゅげむ</rt></ruby>" in html


def test_render_markdown_fragment_supports_nested_numbered_lists():
    html = render_markdown_fragment("1. 数字の\n1. 箇条書きも\n  1. 色々\n  1. 書いたり\n1. できます")

    assert "<li>数字の" in html
    assert "<li>箇条書きも" in html
    assert "<li>色々" in html
    assert "<li>書いたり" in html
    assert "<li>できます" in html
    assert "<ol>" in html


def test_render_slide_html_keeps_nested_numbered_lists_in_one_block():
    slide = """## Demo

### Left

1. 数字の
1. 箇条書きも
  1. 色々
  1. 書いたり
1. できます

### Right

左右分割もできますよ。
"""

    html = render_slide_html(slide)

    assert "<li>箇条書きも" in html
    assert "<li>色々" in html
    assert "<li>書いたり" in html
    assert "<ol>" in html
    assert "<li>できます" in html


def test_render_slide_html_supports_note_blocks():
    slide = """## Demo

:::note warn
注意してください。
:::
"""

    html = render_slide_html(slide)

    assert "note note-warn" in html
    assert "Warning" in html
    assert "注意してください。" in html
    assert "footer-note" in html


def test_nested_ordered_lists_show_parent_prefixes_in_css():
    css = Path("static/lt.css").read_text(encoding="utf-8")

    assert "counters(item, \".\")" in css
    assert "ol > li::before" in css
    assert "content: counters(item, \".\") \". \";" in css


def test_expanded_columns_increase_font_size():
    css = Path("static/lt.css").read_text(encoding="utf-8")

    assert ".two-col.is-left-expanded .left-column" in css
    assert ".three-col.is-center-expanded .center-column" in css
    assert "font-size: clamp(1.4rem, 1.8vw, 1.7rem);" in css


def test_slide_deck_supports_body_font_scaling_controls():
    template = Path("templates/slide_deck.html.j2").read_text(encoding="utf-8")
    css = Path("static/lt.css").read_text(encoding="utf-8")

    assert "zoom-out" in template
    assert "zoom-in" in template
    assert "--body-font-scale" in css
    assert "body-font-scale" in template


def test_slide_deck_has_timer_start_button_and_second_page_auto_start():
    template = Path("templates/slide_deck.html.j2").read_text(encoding="utf-8")

    assert "timer-start-btn" in template
    assert "startTimer" in template
    assert "currentIndex >= 1" in template


def test_slide_deck_uses_default_5_minute_timer_and_3_minute_toggle():
    template = Path("templates/slide_deck.html.j2").read_text(encoding="utf-8")

    assert "timerModes =" in template
    assert "easy:" in template
    assert "hard:" in template
    assert "timer-mode-toggle" in template
    assert "label: '5'" in template
    assert "label: '3'" in template


def test_timer_env_configuration_supports_easy_and_hard_sets():
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "TIMER_EASY_SECONDS" in env_example
    assert "TIMER_EASY_ALERT_SECONDS" in env_example
    assert "TIMER_HARD_SECONDS" in env_example
    assert "TIMER_HARD_ALERT_SECONDS" in env_example
    assert "TIMER_EASY_SECONDS=300" in env_example
    assert "TIMER_HARD_SECONDS=180" in env_example


def test_render_slide_html_moves_notes_to_footer_in_two_column_layout():
    slide = """## Demo

### Left

- left

### Right

- right

:::note alert
注意してください。
:::
"""

    html = render_slide_html(slide)

    assert "two-col" in html
    assert "footer-note" in html
    assert "note note-alert" in html
    assert "注意してください。" in html
    assert html.index("footer-note") > html.index("two-col")


def test_render_slide_html_keeps_notes_and_quotes_in_footer():
    slide = """## Demo

- body

> 引用元

:::note info
メモです。
:::
"""

    html = render_slide_html(slide)

    assert "footer-note" in html
    assert "引用元" in html
    assert "メモです。" in html
    assert "<li>body</li>" in html
    assert html.index("footer-note") > html.index("<li>body</li>")


def test_build_slide_html_renders_title_meta_right_aligned():
    source = """---
title: \"Deck title\"
author: \"Tatsuki\"
date: \"2026-08-27\"
---

# Deck title

## Intro
"""

    html = __import__("markdown_lt.server", fromlist=["build_slide_html"]).build_slide_html(source)

    assert "title-slide" in html
    assert "title-meta" in html
    assert "Author:" in html
    assert "Date:" in html


def test_build_slide_html_renders_subtitle_under_title():
    source = """---
title: \"Deck title\"
author: \"Tatsuki\"
date: \"2026-08-27\"
---

# Deck title

This is the subtitle.

## Intro
"""

    html = __import__("markdown_lt.server", fromlist=["build_slide_html"]).build_slide_html(source)

    assert "This is the subtitle." in html
    assert "subtitle" in html


def test_build_slide_html_uses_front_matter_without_h1_heading():
    source = """---
title: \"Deck title\"
subtitle: \"This is the subtitle.\"
author: \"Tatsuki\"
date: \"2026-08-27\"
---

## Intro

hello world
"""

    html = __import__("markdown_lt.server", fromlist=["build_slide_html"]).build_slide_html(source)

    assert "Deck title" in html
    assert "This is the subtitle." in html
    assert "<h2>Intro</h2>" in html


def test_create_app_lists_slide_folders_and_opens_a_deck_by_folder_name():
    app = create_app("slides")
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200
    assert "sample-slide" in index.text

    deck = client.get("/slides/sample-slide")
    assert deck.status_code == 200
    assert "サンプルスライド" in deck.text
    assert "これはサブタイトルです" in deck.text


def test_resolve_default_source_points_to_slides_directory():
    default_source = resolve_default_source()
    assert default_source.endswith("slides")
