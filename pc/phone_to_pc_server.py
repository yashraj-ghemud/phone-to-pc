#!/usr/bin/env python3
"""Phone-to-PC gateway.

The server accepts image uploads from the Android app and serves a tiny local
web dashboard. It deliberately uses only the Python standard library so it is
easy to run on Windows, macOS, and Linux.
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import secrets
import shutil
import socket
import threading
import time
import webbrowser
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
UPLOAD_DIR = ROOT / "received"
TOKEN_FILE = ROOT / ".pairing_token"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("phone-to-pc")


@dataclass
class GatewayState:
    started_at: float
    last_upload: dict | None = None
    upload_count: int = 0
    last_device: str | None = None


state = GatewayState(started_at=time.time())
state_lock = threading.Lock()


def get_or_create_token() -> str:
    configured = os.getenv("PHONE_TO_PC_TOKEN", "").strip()
    if configured:
        return configured
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(18)
    TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return token


def local_ip() -> str:
    """Best-effort LAN address for the QR/manual pairing screen."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def safe_filename(name: str) -> str:
    name = Path(name or "capture.jpg").name
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    cleaned = "".join(char if char in allowed else "_" for char in name)
    return cleaned[:100] or "capture.jpg"


def write_upload(handler: BaseHTTPRequestHandler) -> dict:
    try:
        size = int(handler.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if size <= 0 or size > MAX_UPLOAD_BYTES:
        raise ValueError(f"payload must be between 1 and {MAX_UPLOAD_BYTES} bytes")

    original_name = safe_filename(handler.headers.get("X-Filename", "capture.jpg"))
    suffix = Path(original_name).suffix.lower() or ".jpg"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target = UPLOAD_DIR / f"{stamp}_{secrets.token_hex(3)}{suffix}"
    temporary = target.with_suffix(target.suffix + ".part")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    remaining = size
    with temporary.open("wb") as output:
        while remaining:
            chunk = handler.rfile.read(min(64 * 1024, remaining))
            if not chunk:
                raise ConnectionError("client disconnected during upload")
            output.write(chunk)
            remaining -= len(chunk)
    temporary.replace(target)

    item = {
        "filename": target.name,
        "original_name": original_name,
        "size": size,
        "device": handler.headers.get("X-Phone-Name", "Android phone")[:80],
        "received_at": datetime.now(timezone.utc).isoformat(),
        "url": f"/received/{target.name}",
    }
    with state_lock:
        state.last_upload = item
        state.upload_count += 1
        state.last_device = item["device"]
    return item


class Handler(BaseHTTPRequestHandler):
    server_version = "PhoneToPC/1.0"

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        with path.open("rb") as source:
            shutil.copyfileobj(source, self.wfile)

    def authorized(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Phone-Token", ""), self.server.token)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Phone-Token, X-Phone-Name, X-Filename")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/v1/health":
            with state_lock:
                payload = asdict(state)
            payload.update({"ok": True, "max_upload_bytes": MAX_UPLOAD_BYTES})
            self.send_json(payload)
            return
        if path == "/api/v1/pairing":
            self.send_json({"host": self.server.advertised_host, "port": self.server.server_port, "token": self.server.token})
            return
        if path.startswith("/received/"):
            requested = Path(path.removeprefix("/received/")).name
            self.send_file(UPLOAD_DIR / requested)
            return
        requested = "index.html" if path in ("/", "") else path.removeprefix("/")
        requested_path = (STATIC_DIR / requested).resolve()
        if STATIC_DIR not in requested_path.parents and requested_path != STATIC_DIR:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_file(requested_path)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/v1/upload":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.authorized():
            self.send_json({"ok": False, "error": "invalid pairing token"}, HTTPStatus.UNAUTHORIZED)
            return
        try:
            item = write_upload(self)
        except (ValueError, ConnectionError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except OSError:
            log.exception("failed to write upload")
            self.send_json({"ok": False, "error": "server could not save the upload"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        log.info("received %s from %s", item["filename"], item["device"])
        self.send_json({"ok": True, "file": item}, HTTPStatus.CREATED)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], token: str, advertised_host: str):
        super().__init__(address, Handler)
        self.token = token
        self.advertised_host = advertised_host


def main() -> None:
    parser = argparse.ArgumentParser(description="Receive images from the Phone-to-PC Android app")
    parser.add_argument("--host", default="0.0.0.0", help="interface to bind; use 127.0.0.1 for same-PC testing")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    token = get_or_create_token()
    server = Server((args.host, args.port), token, local_ip() if args.host == "0.0.0.0" else args.host)
    url = f"http://{server.advertised_host}:{server.server_port}"
    print("\nPHONE-TO-PC GATEWAY")
    print(f"Dashboard : {url}")
    print(f"Upload API: {url}/api/v1/upload")
    print(f"Pair token: {token}")
    print(f"Received  : {UPLOAD_DIR}\n")
    log.info("server listening on %s", server.server_address)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping gateway...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
