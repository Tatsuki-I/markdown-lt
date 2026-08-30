from __future__ import annotations

import argparse
import socket
from pathlib import Path

import uvicorn

from .server import create_app


def get_available_port(port: int) -> int:
    """Return the requested port unless it is already occupied, then use the next free one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            next_port = port + 1
            while True:
                try:
                    sock.bind(("127.0.0.1", next_port))
                    return next_port
                except OSError:
                    next_port += 1


def resolve_default_source() -> str:
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / "slides")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a Markdown slide deck with live preview.")
    parser.add_argument("source", nargs="?", default=resolve_default_source())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--theme", choices=["default", "light", "solarized"], default="default")
    args = parser.parse_args()

    port = get_available_port(args.port)
    app = create_app(args.source, theme_name=args.theme)
    print(f"Starting markdown-lt on http://{args.host}:{port}")
    uvicorn.run(app, host=args.host, port=port, reload=False)


if __name__ == "__main__":
    main()
