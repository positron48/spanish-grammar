#!/usr/bin/env python3
import argparse
import json
import posixpath
import re
import subprocess
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sanitize_rel_path(raw: str) -> str:
    norm = posixpath.normpath("/" + (raw or "")).lstrip("/")
    if norm.startswith("../") or norm == "..":
        raise ValueError("path traversal denied")
    return norm


class TrainingPackStore:
    def __init__(self, course_root: Path):
        self.course_root = course_root.resolve()
        self.pack_root = (self.course_root / "training_pack").resolve()
        self.pack_chapters_root = (self.pack_root / "chapters").resolve()
        self.chapters_root = (self.course_root / "chapters").resolve()
        self.repo_root = self._detect_repo_root()

    def _detect_repo_root(self) -> Path | None:
        try:
            cp = subprocess.run(
                ["git", "-C", str(self.course_root), "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
            )
            out = cp.stdout.strip()
            return Path(out).resolve() if out else None
        except Exception:
            return None

    def _resolve_pack_rel_file(self, rel_file: str) -> Path:
        safe = sanitize_rel_path(rel_file)
        p = (self.pack_chapters_root / safe).resolve()
        if self.pack_chapters_root not in p.parents:
            raise ValueError("invalid path")
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"file not found: {safe}")
        return p

    def list_question_files(self):
        git_statuses = self._git_status_map()
        out = []
        for folder in sorted(self.pack_chapters_root.glob("*")):
            if not folder.is_dir():
                continue
            for f in sorted(folder.glob("*.questions.json")):
                rel = f.relative_to(self.pack_chapters_root).as_posix()
                git_summary = self._git_file_status(f, git_statuses)
                out.append(
                    {
                        "folder": folder.name,
                        "file": f.name,
                        "rel_path": rel,
                        "size": f.stat().st_size,
                        "git": git_summary,
                    }
                )
        return out

    def _repo_rel(self, file_path: Path) -> str | None:
        if self.repo_root is None:
            return None
        try:
            return file_path.resolve().relative_to(self.repo_root).as_posix()
        except Exception:
            return None

    def _git_status_map(self) -> dict:
        if self.repo_root is None:
            return {}
        rel_chapters = self.pack_chapters_root.relative_to(self.repo_root).as_posix()
        try:
            cp = subprocess.run(
                ["git", "-C", str(self.repo_root), "status", "--porcelain", "--", rel_chapters],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return {}
        out = {}
        for line in cp.stdout.splitlines():
            if not line.strip():
                continue
            code = line[:2]
            path_part = line[3:].strip()
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1].strip()
            path_part = path_part.strip('"')
            if code == "??":
                out[path_part] = "new"
            else:
                out[path_part] = "modified"
        return out

    def _git_file_status(self, file_path: Path, statuses: dict) -> dict:
        repo_rel = self._repo_rel(file_path)
        status = "clean"
        if repo_rel:
            status = statuses.get(repo_rel, "clean")
            # If git status reports an untracked/modified directory path (e.g. ".../003/"),
            # treat all nested files as having the same status.
            if status == "clean":
                for pfx, st in statuses.items():
                    if pfx.endswith("/") and repo_rel.startswith(pfx):
                        status = st
                        break
        return {
            "available": self.repo_root is not None,
            "status": status,  # clean | new | modified
            "is_new": status == "new",
            "is_modified": status == "modified",
        }

    def _find_course_chapter_file(self, chapter_id: str) -> Path | None:
        for chapter_dir in sorted(self.chapters_root.glob("*")):
            if not chapter_dir.is_dir():
                continue
            for name in ("05-final.json", "04-final.json"):
                p = chapter_dir / name
                if not p.exists():
                    continue
                try:
                    chapter_payload = read_json(p)
                except Exception:
                    continue
                if chapter_payload.get("id") == chapter_id:
                    return p
        return None

    @staticmethod
    def _extract_theory_block(chapter_payload: dict, theory_block_id: str):
        for block in chapter_payload.get("blocks", []):
            if not isinstance(block, dict):
                continue
            if block.get("type") != "theory" or block.get("id") != theory_block_id:
                continue
            theory = block.get("theory", {}) if isinstance(block.get("theory"), dict) else {}
            return {
                "id": block.get("id"),
                "title": block.get("title", ""),
                "content_md": theory.get("content_md", ""),
                "key_points": theory.get("key_points", []),
                "common_mistakes": theory.get("common_mistakes", []),
                "examples": theory.get("examples", []),
                "concept_id": theory.get("concept_id", ""),
            }
        return None

    def load_question_file(self, rel_file: str):
        p = self._resolve_pack_rel_file(rel_file)
        payload = read_json(p)
        chapter_id = payload.get("chapter_id", "")
        theory_block_id = payload.get("theory_block_id", "")
        chapter_file = self._find_course_chapter_file(chapter_id) if chapter_id else None
        theory_block = None
        if chapter_file is not None:
            chapter_payload = read_json(chapter_file)
            theory_block = self._extract_theory_block(chapter_payload, theory_block_id)
        git_info = self._git_question_changes(p, payload)
        git_info["file_status"] = self._git_file_status(p, self._git_status_map())
        return {
            "rel_path": rel_file,
            "absolute_path": str(p),
            "payload": payload,
            "theory_block": theory_block,
            "theory_source_file": str(chapter_file) if chapter_file else None,
            "git": git_info,
        }

    @staticmethod
    def _question_key(q: dict, idx: int) -> str:
        qid = str(q.get("id", "")).strip()
        if qid:
            return f"id:{qid}"
        sig = str(q.get("signature", "")).strip()
        if sig:
            return f"sig:{sig}"
        return f"idx:{idx}"

    @staticmethod
    def _question_fingerprint(q: dict) -> str:
        return json.dumps(q, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _git_show_head_file(self, file_path: Path) -> dict | None:
        repo_rel = self._repo_rel(file_path)
        if self.repo_root is None or repo_rel is None:
            return None
        tracked = subprocess.run(
            ["git", "-C", str(self.repo_root), "ls-files", "--error-unmatch", repo_rel],
            capture_output=True,
            text=True,
        )
        if tracked.returncode != 0:
            return None
        show = subprocess.run(
            ["git", "-C", str(self.repo_root), "show", f"HEAD:{repo_rel}"],
            capture_output=True,
            text=True,
        )
        if show.returncode != 0 or not show.stdout.strip():
            return None
        try:
            return json.loads(show.stdout)
        except Exception:
            return None

    def _git_question_changes(self, file_path: Path, current_payload: dict) -> dict:
        current_qs = current_payload.get("questions", [])
        if not isinstance(current_qs, list):
            current_qs = []
        head_payload = self._git_show_head_file(file_path)
        if head_payload is None:
            statuses = {}
            for i, q in enumerate(current_qs):
                if isinstance(q, dict):
                    statuses[self._question_key(q, i)] = "new"
            return {
                "available": self.repo_root is not None,
                "question_status": statuses,
                "new_count": len(statuses),
                "changed_count": 0,
                "total_changed": len(statuses),
            }

        head_qs = head_payload.get("questions", [])
        if not isinstance(head_qs, list):
            head_qs = []
        head_by_key = {}
        for i, q in enumerate(head_qs):
            if isinstance(q, dict):
                head_by_key[self._question_key(q, i)] = q

        statuses = {}
        new_count = 0
        changed_count = 0
        for i, q in enumerate(current_qs):
            if not isinstance(q, dict):
                continue
            key = self._question_key(q, i)
            old = head_by_key.get(key)
            if old is None:
                statuses[key] = "new"
                new_count += 1
                continue
            if self._question_fingerprint(old) != self._question_fingerprint(q):
                statuses[key] = "changed"
                changed_count += 1
        return {
            "available": True,
            "question_status": statuses,
            "new_count": new_count,
            "changed_count": changed_count,
            "total_changed": new_count + changed_count,
        }

    def delete_question(self, rel_file: str, question_id: str):
        p = self._resolve_pack_rel_file(rel_file)
        payload = read_json(p)
        questions = payload.get("questions", [])
        if not isinstance(questions, list):
            raise ValueError("questions is not a list")
        before = len(questions)
        kept = [q for q in questions if str(q.get("id", "")) != str(question_id)]
        removed = before - len(kept)
        if removed <= 0:
            raise KeyError(f"question not found: {question_id}")
        payload["questions"] = kept
        write_json(p, payload)
        return {"removed": removed, "remaining": len(kept)}


class Handler(BaseHTTPRequestHandler):
    store: TrainingPackStore = None  # set in run()
    static_dir: Path = None  # set in run()
    route_re = re.compile(r"^/\d{3}/\d{2}/?$")

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

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/files":
                self._send_json(200, {"files": self.store.list_question_files()})
                return
            if path == "/api/file":
                rel_file = (qs.get("path") or [""])[0]
                if not rel_file:
                    self._send_json(400, {"error": "missing query: path"})
                    return
                self._send_json(200, self.store.load_question_file(rel_file))
                return
            if path in ("/", "/index.html") or self.route_re.match(path):
                self._send_file(self.static_dir / "index.html", "text/html; charset=utf-8")
                return
            self._send_json(404, {"error": "not found"})
        except FileNotFoundError as e:
            self._send_json(404, {"error": str(e)})
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/delete-question":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            data = json.loads(raw.decode("utf-8"))
            rel_file = data.get("path")
            question_id = data.get("question_id")
            if not rel_file or not question_id:
                self._send_json(400, {"error": "path and question_id are required"})
                return
            result = self.store.delete_question(rel_file, question_id)
            self._send_json(200, result)
        except KeyError as e:
            self._send_json(404, {"error": str(e)})
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    def log_message(self, fmt: str, *args):
        # Quieter logs, still useful while debugging.
        print(f"[training-pack-admin] {self.address_string()} - {fmt % args}")


def run():
    parser = argparse.ArgumentParser(description="Lightweight training_pack browser/editor (no build)")
    parser.add_argument("--course-root", default=".", help="Path to courses/spanish-grammar root")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()

    course_root = Path(args.course_root).resolve()
    static_dir = Path(__file__).resolve().parent
    store = TrainingPackStore(course_root=course_root)

    Handler.store = store
    Handler.static_dir = static_dir

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"training-pack-admin started: http://127.0.0.1:{args.port}/")
    print(f"course root: {course_root}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
