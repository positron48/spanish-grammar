#!/usr/bin/env python3
import argparse
import json
import re
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ManualTextsStore:
    def __init__(self, course_root: Path):
        self.texts_root = (course_root.resolve() / "manual-texts").resolve()
        if not self.texts_root.is_dir():
            raise FileNotFoundError(f"manual-texts directory not found: {self.texts_root}")

    def _resolve_name(self, name: str) -> Path:
        safe = Path(name).name
        if safe != name or not safe.endswith(".json"):
            raise ValueError("invalid file name")
        p = (self.texts_root / safe).resolve()
        if p.parent != self.texts_root:
            raise ValueError("invalid path")
        return p

    def list_files(self):
        out = []
        for f in sorted(self.texts_root.glob("*.json"), key=self._sort_key):
            out.append({"name": f.name, "size": f.stat().st_size})
        return out

    @staticmethod
    def _sort_key(path: Path):
        m = re.fullmatch(r"(\d+)\.json", path.name)
        return (0, int(m.group(1))) if m else (1, path.name)

    def load_file(self, name: str):
        p = self._resolve_name(name)
        if not p.exists():
            raise FileNotFoundError(f"file not found: {name}")
        return {"name": p.name, "content": read_json(p)}

    def create_file(self, raw_text: str):
        text = (raw_text or "").strip()
        if not text:
            raise ValueError("empty JSON")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSON: {e}") from e
        if not isinstance(payload, dict):
            raise ValueError("JSON root must be an object")
        name = self._next_file_name()
        p = self.texts_root / name
        write_json(p, payload)
        return {"name": name, "content": payload}

    def _next_file_name(self) -> str:
        max_num = 0
        for f in self.texts_root.glob("*.json"):
            m = re.fullmatch(r"(\d+)\.json", f.name)
            if m:
                max_num = max(max_num, int(m.group(1)))
        return f"{max_num + 1}.json"


class Handler(BaseHTTPRequestHandler):
    store: ManualTextsStore = None
    static_dir: Path = None

    def _send_json(self, status: int, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path, content_type: str):
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/files":
                self._send_json(200, {"files": self.store.list_files()})
                return
            if path == "/api/file":
                name = (qs.get("name") or [""])[0]
                if not name:
                    self._send_json(400, {"error": "missing query: name"})
                    return
                self._send_json(200, self.store.load_file(name))
                return
            if path in ("/", "/index.html"):
                self._send_file(self.static_dir / "index.html", "text/html; charset=utf-8")
                return
            self._send_json(404, {"error": "not found"})
        except FileNotFoundError as e:
            self._send_json(404, {"error": str(e)})
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/create":
            self._send_json(404, {"error": "not found"})
            return
        try:
            data = self._read_json_body()
            result = self.store.create_file(str(data.get("text", "")))
            self._send_json(201, result)
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    def log_message(self, fmt: str, *args):
        print(f"[manual-texts-admin] {self.address_string()} - {fmt % args}")


def run():
    parser = argparse.ArgumentParser(description="Mini admin for manual-texts/*.json")
    parser.add_argument("--course-root", default=".", help="Path to courses/spanish-grammar root")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()

    course_root = Path(args.course_root).resolve()
    static_dir = Path(__file__).resolve().parent
    store = ManualTextsStore(course_root=course_root)

    Handler.store = store
    Handler.static_dir = static_dir

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"manual-texts-admin started: http://127.0.0.1:{args.port}/")
    print(f"manual-texts: {store.texts_root}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
