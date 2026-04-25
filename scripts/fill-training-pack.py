#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def log(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts}: {message}", flush=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(v):
    if v is None:
        return ""
    t = str(v).strip().lower()
    # Remove quote variants to avoid signature mismatch on typography only.
    t = re.sub(r"[\"'`´«»„“”‘’‚‛‹›]", "", t)
    return " ".join(t.split())


def question_signature(q: dict) -> str:
    correct_answer_id = q.get("correct_answer")
    correct_answer_text = ""
    choices = q.get("choices")
    if isinstance(choices, list) and correct_answer_id is not None:
        for c in choices:
            if not isinstance(c, dict):
                continue
            if c.get("id") == correct_answer_id:
                correct_answer_text = c.get("text", "")
                break
    if not normalize_text(correct_answer_text):
        correct_answer_text = correct_answer_id
    parts = [
        normalize_text(q.get("prompt")),
        normalize_text(correct_answer_text),
        normalize_text(q.get("theory_block_id")),
        normalize_text(q.get("type")),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def renumber_question_ids(questions: List[dict]):
    idx = 1
    for q in questions:
        if not isinstance(q, dict):
            continue
        q["id"] = f"q{idx}"
        idx += 1


def has_cyrillic(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x0400 <= code <= 0x04FF:
            return True
    return False


def read_final_json(chapter_dir: Path):
    for name in ("05-final.json", "04-final.json"):
        p = chapter_dir / name
        if p.exists():
            return read_json(p)
    return None


def load_chapters(course_root: Path):
    chapters_dir = course_root / "chapters"
    chapter_dirs = [p for p in chapters_dir.iterdir() if p.is_dir()]
    chapter_dirs.sort()
    out = []
    for idx, chapter_dir in enumerate(chapter_dirs, start=1):
        chapter = read_final_json(chapter_dir)
        if not chapter or not chapter.get("id"):
            continue
        chapter["__index"] = idx
        out.append(chapter)
    return out


def theory_blocks(chapter: dict):
    out = []
    for b in chapter.get("blocks", []):
        if not isinstance(b, dict) or b.get("type") != "theory" or not b.get("id"):
            continue
        out.append({"index": len(out) + 1, "id": b["id"]})
    return out


def load_env_local(course_root: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env_path = course_root / ".env.local"
    if not env_path.exists():
        return env
    pattern = re.compile(r'^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$')
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = pattern.match(line)
        if not m:
            continue
        key, raw_val = m.group(1), m.group(2).strip()
        if (raw_val.startswith('"') and raw_val.endswith('"')) or (raw_val.startswith("'") and raw_val.endswith("'")):
            raw_val = raw_val[1:-1]
        env[key] = raw_val
    return env


def find_block_pack_file(pack_dir: Path, chapter_id: str, block_id: str) -> Path | None:
    idx_path = pack_dir / "index.json"
    if idx_path.exists():
        idx = read_json(idx_path)
        rel = idx.get("blocks", {}).get(f"{chapter_id}::{block_id}")
        if rel:
            p = pack_dir / "chapters" / rel
            if p.exists():
                return p
    candidates = sorted((pack_dir / "chapters").glob(f"*/es.*.{block_id}.questions.json"))
    if candidates:
        return candidates[-1]
    return None


def is_valid_question_for_block(q: dict, chapter_id: str, block_id: str) -> bool:
    """
    Согласовано с validate_question() в generate-training-pack.py: кириллица в
    prompt и explanation; choices могут быть на испанском (только непустой text;
    ровно 4 варианта, id a–d), иначе fill считал +0 валидных при «accepted>0».
    """
    if not isinstance(q, dict):
        return False
    if q.get("type") != "mcq_single":
        return False
    if q.get("chapter_id") != chapter_id:
        return False
    if q.get("theory_block_id") != block_id:
        return False
    if not has_cyrillic(str(q.get("prompt", ""))):
        return False
    if not has_cyrillic(str(q.get("explanation", ""))):
        return False
    choices = q.get("choices")
    if not isinstance(choices, list) or len(choices) != 4:
        return False
    allowed = {"a", "b", "c", "d"}
    ids = []
    for c in choices:
        if not isinstance(c, dict):
            return False
        cid = c.get("id")
        ctext = c.get("text")
        if not cid or not str(ctext).strip():
            return False
        ids.append(cid)
    if set(ids) != allowed:
        return False
    return q.get("correct_answer") in allowed


def recalc_signatures_and_dedupe_block_file(cp: Path) -> int:
    payload = read_json(cp)
    questions = payload.get("questions", [])
    if not isinstance(questions, list):
        return 0
    seen = set()
    kept = []
    removed = 0
    for q in questions:
        if not isinstance(q, dict):
            removed += 1
            continue
        sig = question_signature(q)
        q["signature"] = sig
        if sig in seen:
            removed += 1
            continue
        seen.add(sig)
        kept.append(q)
    if removed > 0:
        payload["questions"] = kept
        renumber_question_ids(payload["questions"])
        write_json(cp, payload)
    return removed


def count_valid_for_block(course_root: Path, chapter_id: str, block_id: str) -> int:
    pack_dir = course_root / "training_pack"
    cp = find_block_pack_file(pack_dir, chapter_id, block_id)
    if cp is None:
        return 0
    removed = recalc_signatures_and_dedupe_block_file(cp)
    if removed > 0:
        log(f"[BLOCK] dedupe by signature in {cp.name}: removed={removed}")
    payload = read_json(cp)
    cnt = 0
    for q in payload.get("questions", []):
        if is_valid_question_for_block(q, chapter_id, block_id):
            cnt += 1
    return cnt


def run_generator(course_root: Path, env: Dict[str, str], chapter_number: int, block_number: int, batch_size: int) -> int:
    cmd = [
        "python3",
        "scripts/generate-training-pack.py",
        "--course-root",
        str(course_root),
        "--chapter-number",
        str(chapter_number),
        "--block-number",
        str(block_number),
        "--questions-per-block",
        str(batch_size),
        "--append",
    ]
    proc = subprocess.run(cmd, cwd=str(course_root), env=env)
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description="Fill all Spanish theory blocks up to target valid questions")
    parser.add_argument("--course-root", default=".")
    parser.add_argument("--batch-size", type=int, default=3, help="How many new questions per generator call")
    parser.add_argument("--target-valid", type=int, default=20, help="Stop per block when valid count reaches this number")
    parser.add_argument("--max-rounds-per-block", type=int, default=50, help="Safety guard to avoid infinite loops")
    parser.add_argument("--chapter-number", type=int, default=0, help="Optional single chapter filter (1-based)")
    parser.add_argument("--block-number", type=int, default=0, help="Optional single block filter (1-based, requires chapter filter)")
    args = parser.parse_args()

    course_root = Path(args.course_root).resolve()
    env = load_env_local(course_root)
    chapters = load_chapters(course_root)

    if args.block_number and not args.chapter_number:
        raise SystemExit("--block-number requires --chapter-number")

    total_blocks = 0
    completed_blocks = 0
    failed_blocks = 0

    for chapter in chapters:
        chapter_idx = int(chapter.get("__index", 0))
        if args.chapter_number and chapter_idx != args.chapter_number:
            continue
        chapter_id = chapter["id"]
        blocks = theory_blocks(chapter)
        for block in blocks:
            block_idx = int(block["index"])
            if args.block_number and block_idx != args.block_number:
                continue
            total_blocks += 1
            block_id = block["id"]
            current = count_valid_for_block(course_root, chapter_id, block_id)
            log(f"[BLOCK] chapter#{chapter_idx} block#{block_idx} {chapter_id}/{block_id} current_valid={current} target={args.target_valid}")
            rounds = 0
            success = True
            zero_gain_streak = 0
            while current < args.target_valid and rounds < args.max_rounds_per_block:
                rounds += 1
                log(f"[BLOCK] round {rounds}: generate batch={args.batch_size}")
                code = run_generator(course_root, env, chapter_idx, block_idx, args.batch_size)
                if code != 0:
                    log(f"[BLOCK] generation failed with exit_code={code}")
                    success = False
                    break
                next_count = count_valid_for_block(course_root, chapter_id, block_id)
                gained = next_count - current
                current = next_count
                log(f"[BLOCK] round {rounds} done: +{gained} valid, total={current}")
                if gained > 0:
                    zero_gain_streak = 0
                else:
                    zero_gain_streak += 1
                    if zero_gain_streak >= 2:
                        log("[BLOCK] no progress in 2 consecutive rounds; stopping block")
                        success = False
                        break
                    log("[BLOCK] no new valid questions this round; one more generation attempt for this block")
            if current >= args.target_valid:
                completed_blocks += 1
                log(f"[BLOCK] reached target: {current}/{args.target_valid}")
            else:
                failed_blocks += 1
                if success and rounds >= args.max_rounds_per_block:
                    log(f"[BLOCK] max rounds reached: {current}/{args.target_valid}")
                else:
                    log(f"[BLOCK] incomplete: {current}/{args.target_valid}")

    log(f"[SUMMARY] blocks_total={total_blocks} completed={completed_blocks} failed={failed_blocks}")
    if failed_blocks > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

