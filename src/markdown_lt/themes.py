from __future__ import annotations

THEMES = {
    "default": {
        "background": "#0f172a",
        "text": "#e2e8f0",
        "accent": "#38bdf8",
        "muted": "#94a3b8",
    },
    "light": {
        "background": "#f8fafc",
        "text": "#0f172a",
        "accent": "#2563eb",
        "muted": "#475569",
    },
    "solarized": {
        "background": "#002b36",
        "text": "#fdf6e3",
        "accent": "#b58900",
        "muted": "#93a1a1",
    },
}


def get_theme(name: str) -> dict[str, str]:
    return THEMES.get(name, THEMES["default"]).copy()
