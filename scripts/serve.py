#!/usr/bin/env python3
"""Static file server for the built oem/links site.

Deliberately dependency-free: the systemd unit runs THIS from the repo
instead of `npx serve`, so starting the service never downloads an
unpinned package from the npm registry at boot.

Usage: serve.py [--bind 0.0.0.0] [--port 8080] [--root dist]
"""

from __future__ import annotations

import argparse
import functools
import http.server
import mimetypes
import os
import socketserver
import sys

# Some minimal Linux images do not map these by default, and every one of
# them is something this site actually serves.
for ext, mime in {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ico": "image/x-icon",
    ".xml": "application/xml; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}.items():
    mimetypes.add_type(mime, ext)


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static handler with two site-specific behaviours.

    - directory requests serve index.html (the built site is a single page)
    - a missing path returns a real 404 instead of a directory listing
    """

    def send_head(self):  # noqa: D102
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            self.path = os.path.join(self.path, "index.html")
        if not os.path.exists(self.translate_path(self.path)):
            self.send_error(404, "Not Found")
            return None
        return super().send_head()

    def end_headers(self) -> None:
        # The site is pure static output; never let a stale asset survive a
        # rebuild, and never let a proxy cache a page we just changed.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stderr.flush()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--root",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist"),
    )
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isfile(os.path.join(root, "index.html")):
        print(f"error: {root}/index.html not found - run `npm run build` first", file=sys.stderr)
        return 1

    handler = functools.partial(Handler, directory=root)
    with Server((args.bind, args.port), handler) as httpd:
        print(f"==> serving {root} on http://{args.bind}:{args.port}/", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
