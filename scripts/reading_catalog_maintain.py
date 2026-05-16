#!/usr/bin/env python3
"""
Maintain free reading drafts under <course-root>/<draft-dir>/:
- Remove texts with fewer than MIN_WORDS word tokens (Unicode \\w+ in segment `text` only).
- Remove duplicate titles (casefold + whitespace-normalized): keep the text with the highest
  word count; on tie keep lexicographically smallest text_id.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
import time
from collections import defaultdict
from typing import Any

WORD_RE = re.compile(r"\w+", re.UNICODE)


def normalize_title(title: str) -> str:
    return " ".join((title or "").casefold().split())


def read_doc_title(doc: dict[str, Any]) -> str:
    rp = doc.get("reading_passage") or {}
    return str(doc.get("title") or rp.get("title") or "").strip()


def word_count_from_doc(doc: dict[str, Any]) -> int:
    rp = doc.get("reading_passage") or {}
    segs = rp.get("segments") or []
    parts: list[str] = []
    for seg in segs:
        if isinstance(seg, dict):
            parts.append(str(seg.get("text") or ""))
    return len(WORD_RE.findall(" ".join(parts)))


def load_reading_index(course_root: pathlib.Path, draft_dir: str) -> tuple[dict[str, Any] | None, pathlib.Path]:
    index_path = course_root / draft_dir / "index.json"
    if not index_path.exists():
        return None, index_path
    return json.loads(index_path.read_text(encoding="utf-8")), index_path


def _rewrite_index(index_path: pathlib.Path, idx: dict[str, Any]) -> None:
    idx["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _remove_text_files(course_root: pathlib.Path, draft_dir: str, idx: dict[str, Any], text_id: str, rel_path: str) -> None:
    if ".." in rel_path or rel_path.startswith(("/")):
        raise ValueError(f"invalid reading text path: {rel_path!r}")
    reading_root = course_root / draft_dir
    text_path = reading_root / pathlib.Path(rel_path)
    if text_path.exists():
        text_path.unlink()

    texts_map = idx.setdefault("texts", {})
    texts_map.pop(text_id, None)

    for cat in list(idx.get("categories", {}).values()):
        tids = list(cat.get("text_ids") or [])
        cat["text_ids"] = [t for t in tids if t != text_id]

    empty_cat_ids = [cid for cid, c in idx.get("categories", {}).items() if not (c.get("text_ids") or [])]
    for cid in empty_cat_ids:
        idx["categories"].pop(cid, None)

    assets_dir = course_root / "assets" / "reading" / text_id
    if assets_dir.exists():
        shutil.rmtree(assets_dir, ignore_errors=True)


def scan_reading_catalog_issues(
    course_root: pathlib.Path, draft_dir: str = "reading", min_words: int = 40
) -> list[str]:
    idx, _ = load_reading_index(course_root, draft_dir)
    if not idx or not idx.get("texts"):
        return []
    issues: list[str] = []
    reading_root = course_root / draft_dir

    by_title: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for text_id in sorted(idx["texts"].keys()):
        rel = idx["texts"][text_id]
        path = reading_root / pathlib.Path(rel_path_safe(rel))
        if not path.exists():
            issues.append(f"{text_id}: missing json {rel}")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            issues.append(f"{text_id}: invalid json ({e})")
            continue
        title = read_doc_title(doc)
        nt = normalize_title(title)
        wc = word_count_from_doc(doc)
        if nt:
            by_title[nt].append((text_id, wc))
        if wc < min_words:
            issues.append(f"{text_id}: too_short words={wc} (<{min_words}) title={title!r}")

    for nt, rows in sorted(by_title.items()):
        if len(rows) <= 1:
            continue
        rows_sorted = sorted(rows, key=lambda r: (-r[1], r[0]))
        keeper = rows_sorted[0][0]
        for tid, _wc in rows_sorted[1:]:
            issues.append(f"{tid}: duplicate_title {nt!r} (keep {keeper})")

    return issues


def rel_path_safe(rel: str) -> str:
    if ".." in rel or rel.startswith("/"):
        raise ValueError(f"invalid rel path: {rel!r}")
    return rel


def prune_reading_catalog(
    course_root: pathlib.Path, draft_dir: str = "reading", min_words: int = 40, dry_run: bool = False
) -> list[str]:
    """Apply duplicate-title and minimum-word rules; returns deleted text_ids."""
    idx, index_path = load_reading_index(course_root, draft_dir)
    if not idx or not idx.get("texts"):
        return []

    reading_root = course_root / draft_dir
    to_delete: set[str] = set()

    # Load metadata per text
    meta: dict[str, dict[str, Any]] = {}
    for text_id in sorted(idx["texts"].keys()):
        rel = idx["texts"][text_id]
        path = reading_root / pathlib.Path(rel_path_safe(rel))
        if not path.exists():
            to_delete.add(text_id)
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            to_delete.add(text_id)
            continue
        title = read_doc_title(doc)
        wc = word_count_from_doc(doc)
        meta[text_id] = {"rel": rel, "nt": normalize_title(title), "wc": wc, "title": title}

    # Duplicate titles: keep best (max words, then smallest text_id)
    by_title: dict[str, list[str]] = defaultdict(list)
    for tid, m in meta.items():
        nt = m["nt"]
        if nt:
            by_title[nt].append(tid)
    for nt, tids in by_title.items():
        if len(tids) <= 1:
            continue
        best = sorted(tids, key=lambda tid: (-meta[tid]["wc"], tid))[0]
        for tid in tids:
            if tid != best:
                to_delete.add(tid)

    # Too short (among not already marked)
    for tid, m in meta.items():
        if tid in to_delete:
            continue
        if m["wc"] < min_words:
            to_delete.add(tid)

    deleted: list[str] = []
    for tid in sorted(to_delete):
        rel = idx.get("texts", {}).get(tid) or meta.get(tid, {}).get("rel")
        if not rel:
            idx.setdefault("texts", {}).pop(tid, None)
            deleted.append(tid)
            continue
        if dry_run:
            deleted.append(tid)
            continue
        _remove_text_files(course_root, draft_dir, idx, tid, rel)
        deleted.append(tid)

    if not dry_run and deleted:
        _rewrite_index(index_path, idx)

    return deleted


def existing_display_titles(
    course_root: pathlib.Path, draft_dir: str = "reading", limit: int = 40
) -> list[str]:
    """Human-readable titles already in catalog (for LLM de-duplication hints)."""
    idx, _ = load_reading_index(course_root, draft_dir)
    if not idx:
        return []
    reading_root = course_root / draft_dir
    titles: list[str] = []
    for _text_id, rel in idx.get("texts", {}).items():
        path = reading_root / pathlib.Path(rel_path_safe(rel))
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        t = read_doc_title(doc)
        if t:
            titles.append(t)
    titles.sort(key=lambda s: normalize_title(s))
    return titles[: max(1, limit)]


def existing_normalized_titles(course_root: pathlib.Path, draft_dir: str = "reading") -> set[str]:
    idx, _ = load_reading_index(course_root, draft_dir)
    if not idx:
        return set()
    reading_root = course_root / draft_dir
    out: set[str] = set()
    for text_id, rel in idx.get("texts", {}).items():
        path = reading_root / pathlib.Path(rel_path_safe(rel))
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        nt = normalize_title(read_doc_title(doc))
        if nt:
            out.add(nt)
    return out


def word_count_from_generated_segments(generated: dict[str, Any]) -> int:
    parts: list[str] = []
    for seg in generated.get("segments") or []:
        if isinstance(seg, dict):
            parts.append(str(seg.get("text") or ""))
    return len(WORD_RE.findall(" ".join(parts)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/prune free reading catalog JSON + audio.")
    parser.add_argument("--course-root", default=".", type=pathlib.Path)
    parser.add_argument("--draft-dir", default="reading")
    parser.add_argument("--min-words", type=int, default=40)
    parser.add_argument("--check", action="store_true", help="Only report issues, exit 1 if any")
    parser.add_argument("--apply", action="store_true", help="Delete invalid texts and rewrite index")
    args = parser.parse_args()
    root = args.course_root.resolve()
    if args.check and args.apply:
        print("use either --check or --apply", file=sys.stderr)
        return 2
    if args.check:
        issues = scan_reading_catalog_issues(root, args.draft_dir, args.min_words)
        if issues:
            for line in issues:
                print(line)
            return 1
        print("reading catalog OK")
        return 0
    if args.apply:
        deleted = prune_reading_catalog(root, args.draft_dir, args.min_words, dry_run=False)
        if deleted:
            print(f"deleted {len(deleted)} reading text(s): {', '.join(deleted)}")
        else:
            print("nothing to prune")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
