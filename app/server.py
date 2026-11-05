"""Local human-entered maintenance evidence, with an optional Meta Muse copilot route. No robot integration."""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import copilot

STATIC = Path(__file__).with_name("static")
DEFAULT_DATA = Path(__file__).resolve().parents[1] / ".artifacts/maintenance-watch"
# One BenBen inspection run, read-only. Media stays in the gitignored .artifacts folder, never in git.
DEFAULT_RUN = Path(__file__).resolve().parents[1] / ".artifacts/benben-runs/20261105T002653Z"
RUN_FILE = re.compile(r"/run/(lidar_iso\.png|map\.png|lidar_split\.mp4|verdicts-pass[12]\.json|frames/\d{3}\.jpg"
                      r"|clips/(1-steps-no-ramp|2-paper-bag|3-chair-laptop|4-entrance-step)\.mp4)")
RUN_TYPES = {"png": "image/png", "jpg": "image/jpeg", "mp4": "video/mp4", "json": "application/json"}
STATUSES = ("new", "acknowledged", "in_progress", "resolved", "dismissed")
MAX_IMAGE = 5 * 1024 * 1024
MAX_REQUEST = 8 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def text_field(data, key, maximum=2000):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{key} must contain 1–{maximum} characters")
    return value.strip()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("observed_at must be an ISO timestamp with a timezone") from None
    if parsed.tzinfo is None:
        raise ValueError("observed_at requires a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.images = self.directory / "images"
        self.images.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "watch.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS maps (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    frame_id TEXT NOT NULL, units TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, notes TEXT NOT NULL,
                    observed_at TEXT NOT NULL, received_at TEXT NOT NULL,
                    source TEXT NOT NULL, timestamp_source TEXT NOT NULL,
                    image_name TEXT NOT NULL, image_sha256 TEXT NOT NULL,
                    map_id TEXT REFERENCES maps(id), x_m REAL, y_m REAL
                );
                CREATE TABLE IF NOT EXISTS issues (
                    id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id),
                    title TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            """)

    def connect(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def snapshot(self):
        with self.connect() as db:
            maps = [dict(row) for row in db.execute("SELECT * FROM maps ORDER BY created_at")]
            observations = [dict(row) for row in db.execute("SELECT * FROM observations ORDER BY received_at DESC")]
            issues = [dict(row) for row in db.execute("SELECT * FROM issues ORDER BY created_at DESC")]
        for observation in observations:
            observation["image_url"] = "/images/" + observation.pop("image_name")
        return {"contract_version": 1, "maps": maps, "observations": observations,
                "issues": issues, "issue_statuses": STATUSES}

    def create_map(self, data):
        name = text_field(data, "name", 100)
        frame = text_field(data, "frame_id", 100)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", frame):
            raise ValueError("frame_id accepts letters, numbers, dots, underscores and hyphens")
        identifier = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO maps VALUES (?,?,?,?,?)", (identifier, name, frame, "m", now()))
        return {"id": identifier}

    def create_observation(self, data):
        title = text_field(data, "title", 150)
        notes = data.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise ValueError("notes must be text of at most 4000 characters")
        observed_at = timestamp(data.get("observed_at"))
        raw = text_field(data, "image_base64", MAX_REQUEST)
        try:
            image = base64.b64decode(raw, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("image_base64 must be valid base64") from None
        if not image or len(image) > MAX_IMAGE:
            raise ValueError("image must be between 1 byte and 5 MiB")
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            extension = "png"
        elif image.startswith(b"\xff\xd8\xff"):
            extension = "jpg"
        elif image.startswith(b"RIFF") and image[8:12] == b"WEBP":
            extension = "webp"
        else:
            raise ValueError("use a PNG, JPEG or WebP image")
        map_id, x, y = data.get("map_id"), data.get("x_m"), data.get("y_m")
        if map_id is not None:
            if not isinstance(map_id, str):
                raise ValueError("map_id must be text")
            import math
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (x, y)):
                raise ValueError("mapped observations require finite x_m and y_m coordinates")
            if max(abs(x), abs(y)) > 100000:
                raise ValueError("map coordinates must be within 100000 meters of the origin")
        elif x is not None or y is not None:
            raise ValueError("coordinates require a map_id")
        identifier = uuid.uuid4().hex
        name = f"{identifier}.{extension}"
        destination = self.images / name
        with self.connect() as db:
            if map_id is not None and not db.execute("SELECT 1 FROM maps WHERE id=?", (map_id,)).fetchone():
                raise ValueError("map_id does not exist")
            try:
                destination.write_bytes(image)
                db.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                    identifier, title, notes, observed_at, now(), "human_upload", "user_entered",
                    name, hashlib.sha256(image).hexdigest(), map_id, x, y))
            except Exception:
                destination.unlink(missing_ok=True)
                raise
        return {"id": identifier}

    def create_issue(self, data):
        observation_id = text_field(data, "observation_id", 32)
        title = text_field(data, "title", 150)
        identifier = uuid.uuid4().hex
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM observations WHERE id=?", (observation_id,)).fetchone():
                raise ValueError("observation_id does not exist")
            created = now()
            db.execute("INSERT INTO issues VALUES (?,?,?,?,?,?)", (identifier, observation_id, title, "new", created, created))
        return {"id": identifier}

    def update_issue(self, identifier, data):
        status = data.get("status")
        if status not in STATUSES:
            raise ValueError("choose a supported issue status")
        with self.connect() as db:
            cursor = db.execute("UPDATE issues SET status=?, updated_at=? WHERE id=?", (status, now(), identifier))
            if cursor.rowcount == 0:
                raise LookupError("issue not found")
        return {"id": identifier, "status": status}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="application/json", length=None, extra=()):
        if content_type == "application/json" and not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body) if length is None else length))
        for name, value in extra:
            self.send_header(name, value)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        if length is None:
            self.wfile.write(body)

    def send_run_file(self, name):
        """Stream one allow-listed run file, honouring a single byte Range so video can seek."""
        file = self.server.run_dir / name
        if not file.is_file():
            self.respond(404, {"error": "run file not found"})
            return
        size = file.stat().st_size
        start, end, status, extra = 0, size - 1, 200, [("Accept-Ranges", "bytes")]
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if match and (match[1] or match[2]):
            if match[1]:
                start, end = int(match[1]), min(int(match[2]) if match[2] else size - 1, size - 1)
            else:
                start = max(size - int(match[2]), 0)
            if start > end:
                self.respond(416, {"error": "range not satisfiable"}, extra=[("Content-Range", f"bytes */{size}")])
                return
            status = 206
            extra.append(("Content-Range", f"bytes {start}-{end}/{size}"))
        self.respond(status, b"", RUN_TYPES[name.rsplit(".", 1)[1]], length=end - start + 1, extra=extra)
        with file.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            try:
                while remaining and (chunk := handle.read(min(remaining, 1 << 20))):
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser dropped a range it no longer needs

    def allowed_request(self):
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origin = self.headers.get("Origin")
        if (self.headers.get("Host") not in hosts
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
                or (origin is not None and origin not in {"http://" + host for host in hosts})):
            self.respond(403, {"error": "request must originate from this local app"})
            return False
        return True

    def do_GET(self):
        if not self.allowed_request():
            return
        path = urlsplit(self.path).path
        if path == "/api/state":
            self.respond(200, self.server.store.snapshot())
        elif path == "/api/copilot/status":
            self.respond(200, copilot.status())
        elif RUN_FILE.fullmatch(path):
            self.send_run_file(path[len("/run/"):])
        elif path in ("/", "/index.html", "/app.js", "/run.js", "/styles.css"):
            name = "index.html" if path == "/" else path[1:]
            types = {"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8"}
            self.respond(200, (STATIC / name).read_bytes(), types[name.split(".")[-1]])
        elif path in ("/fonts/Inter-Latin.woff2", "/fonts/InstrumentSerif-Regular.ttf"):  # OFL fonts, see static/fonts/
            types = {"woff2": "font/woff2", "ttf": "font/ttf"}
            self.respond(200, (STATIC / path[1:]).read_bytes(), types[path.rsplit(".", 1)[1]])
        elif re.fullmatch(r"/images/[0-9a-f]{32}\.(png|jpg|webp)", path):
            filename = path.rsplit("/", 1)[1]
            with self.server.store.connect() as db:
                exists = db.execute("SELECT 1 FROM observations WHERE image_name=?", (filename,)).fetchone()
            if not exists:
                self.respond(404, {"error": "image not found"})
                return
            types = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}
            self.respond(200, (self.server.store.images / filename).read_bytes(), types[filename.rsplit(".", 1)[1]])
        else:
            self.respond(404, {"error": "not found"})

    def do_POST(self):
        if not self.allowed_request():
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.respond(415, {"error": "send application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST:
                self.respond(413, {"error": "request must be between 1 byte and 8 MiB"})
                return
            data = json.loads(self.rfile.read(length), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))
            if not isinstance(data, dict):
                raise ValueError("send a JSON object")
            path = urlsplit(self.path).path
            routes = {"/api/maps": self.server.store.create_map,
                      "/api/observations": self.server.store.create_observation,
                      "/api/issues": self.server.store.create_issue}
            if path in routes:
                result = routes[path](data)
                self.respond(201, result)
            elif path == "/api/copilot":
                self.respond(200, copilot.ask(self.server.store, data, self.server.copilot_provider))
            elif path == "/api/transcribe":
                self.respond(200, copilot.transcribe(data, self.server.asr_provider))
            elif path == "/api/segment":
                self.respond(200, copilot.segment(self.server.store, data, self.server.sam_provider))
            elif re.fullmatch(r"/api/issues/[0-9a-f]{32}/status", path):
                self.respond(200, self.server.store.update_issue(path.split("/")[3], data))
            else:
                self.respond(404, {"error": "not found"})
        except copilot.Unconfigured as error:
            self.respond(503, {"error": str(error), "code": "unconfigured"})
        except copilot.ProviderError as error:
            self.respond(502, {"error": str(error), "code": "provider"})
        except (ValueError, TypeError) as error:
            self.respond(400, {"error": str(error)})
        except LookupError as error:
            self.respond(404, {"error": str(error)})

    def log_message(self, format, *args):
        # Logs method/path/status only, never image or form contents.
        super().log_message(format, *args)


def create_server(directory=DEFAULT_DATA, port=8766, run_dir=DEFAULT_RUN):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.store = Store(directory)
    server.run_dir = Path(run_dir)
    server.copilot_provider = copilot.call_meta  # tests swap in stubs; never a live call
    server.sam_provider = copilot.call_sam
    server.asr_provider = copilot.call_asr
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN, help="BenBen run folder, served read-only under /run/")
    args = parser.parse_args()
    server = create_server(args.data_dir, args.port, args.run_dir)
    print(f"BenBen dashboard: http://127.0.0.1:{server.server_address[1]}", flush=True)
    print(f"Local data: {args.data_dir.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
