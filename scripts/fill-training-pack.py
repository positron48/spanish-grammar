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
from typing import Dict, List


ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_CYAN = "\033[36m"


def log(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts}: {message}", flush=True)


def log_color(message: str, color: str = ""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if color:
        print(f"{color}{ts}: {message}{ANSI_RESET}", flush=True)
    else:
        print(f"{ts}: {message}", flush=True)


def summarize_validation_errors(course_root: Path, chapter_id: str, block_id: str):
    report_path = course_root / "training_pack" / "reports" / "validation-report.json"
    if not report_path.exists():
        log_color("    - validation-report.json не найден", ANSI_YELLOW)
        return
    try:
        report = read_json(report_path)
    except Exception as e:
        log_color(f"    - не удалось прочитать validation-report: {e}", ANSI_YELLOW)
        return

    chapters = report.get("chapters", {})
    chapter_report = chapters.get(chapter_id, {}) if isinstance(chapters, dict) else {}
    errs = chapter_report.get("errors", []) if isinstance(chapter_report, dict) else []
    if not errs:
        log_color("    - явных ошибок по главе в validation-report нет", ANSI_YELLOW)
        return

    printed = 0
    for item in errs:
        if isinstance(item, str):
            log_color(f"    - {item}", ANSI_RED)
            printed += 1
        elif isinstance(item, dict):
            reasons = item.get("errors", [])
            if not reasons:
                continue
            joined = "; ".join(str(r) for r in reasons)
            if block_id in joined or item.get("question_id"):
                qid = item.get("question_id") or "?"
                log_color(f"    - q={qid}: {joined}", ANSI_RED)
                printed += 1
        if printed >= 8:
            break
    if printed == 0:
        log_color("    - детальные причины см. training_pack/reports/validation-report.json", ANSI_YELLOW)


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


def dedupe_choice_texts_keep_correct(q: dict) -> int:
    choices = q.get("choices")
    if not isinstance(choices, list) or not choices:
        return 0
    correct_id = q.get("correct_answer")
    groups = {}
    for idx, c in enumerate(choices):
        if not isinstance(c, dict):
            continue
        key = normalize_text(c.get("text", ""))
        groups.setdefault(key, []).append(idx)
    to_remove = set()
    for _, idxs in groups.items():
        if len(idxs) <= 1:
            continue
        keep_idx = idxs[0]
        for i in idxs:
            c = choices[i] if i < len(choices) else {}
            if isinstance(c, dict) and c.get("id") == correct_id:
                keep_idx = i
                break
        for i in idxs:
            if i != keep_idx:
                to_remove.add(i)
    if not to_remove:
        return 0
    q["choices"] = [c for i, c in enumerate(choices) if i not in to_remove]
    return len(to_remove)


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
    prompt и explanation; choices 2..4 варианта, id только a-d, correct_answer
    должен ссылаться на существующий вариант.
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
    if not isinstance(choices, list) or len(choices) < 2 or len(choices) > 4:
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
    if len(set(ids)) != len(ids):
        return False
    if not set(ids).issubset(allowed):
        return False
    return q.get("correct_answer") in ids


def recalc_signatures_and_dedupe_block_file(cp: Path) -> int:
    payload = read_json(cp)
    questions = payload.get("questions", [])
    if not isinstance(questions, list):
        return 0
    seen = set()
    kept = []
    removed = 0
    removed_invalid_after_choice_dedupe = 0
    removed_choice_dups_total = 0
    for q in questions:
        if not isinstance(q, dict):
            removed += 1
            continue
        removed_choice_dups_total += dedupe_choice_texts_keep_correct(q)
        choices = q.get("choices")
        if not isinstance(choices, list) or len(choices) < 2 or len(choices) > 4:
            removed += 1
            removed_invalid_after_choice_dedupe += 1
            continue
        ids = [c.get("id") for c in choices if isinstance(c, dict)]
        if len(ids) != len(choices):
            removed += 1
            removed_invalid_after_choice_dedupe += 1
            continue
        if len(set(ids)) != len(ids):
            removed += 1
            removed_invalid_after_choice_dedupe += 1
            continue
        if not set(ids).issubset({"a", "b", "c", "d"}):
            removed += 1
            removed_invalid_after_choice_dedupe += 1
            continue
        if q.get("correct_answer") not in ids:
            removed += 1
            removed_invalid_after_choice_dedupe += 1
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
    if removed_choice_dups_total > 0:
        log(
            f"[BLOCK] choices dedupe in {cp.name}: removed_choices={removed_choice_dups_total} "
            f"dropped_questions={removed_invalid_after_choice_dedupe}"
        )
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

    current_chapter_banner = None

    for chapter in chapters:
        chapter_idx = int(chapter.get("__index", 0))
        if args.chapter_number and chapter_idx != args.chapter_number:
            continue
        if current_chapter_banner != chapter_idx:
            current_chapter_banner = chapter_idx
            log_color(f"═══ ГЛАВА {chapter_idx} ═══", ANSI_BOLD)
        chapter_id = chapter["id"]
        blocks = theory_blocks(chapter)
        for block in blocks:
            block_idx = int(block["index"])
            if args.block_number and block_idx != args.block_number:
                continue
            total_blocks += 1
            block_id = block["id"]
            current = count_valid_for_block(course_root, chapter_id, block_id)
            log_color(f"■ Блок {block_idx}: сейчас {current}, цель {args.target_valid}", ANSI_CYAN)
            rounds = 0
            success = True
            zero_gain_streak = 0
            while current < args.target_valid and rounds < args.max_rounds_per_block:
                rounds += 1
                log_color(f"  • Раунд {rounds}: запуск генератора", ANSI_CYAN)
                code = run_generator(course_root, env, chapter_idx, block_idx, args.batch_size)
                if code != 0:
                    log_color(f"    ✗ генератор завершился с кодом {code}", ANSI_RED)
                    summarize_validation_errors(course_root, chapter_id, block_id)
                    success = False
                    break
                next_count = count_valid_for_block(course_root, chapter_id, block_id)
                gained = next_count - current
                current = next_count
                mark = "✓" if gained > 0 else "·"
                color = ANSI_GREEN if gained > 0 else ANSI_YELLOW
                log_color(f"    {mark} раунд {rounds}: +{gained}, всего {current}", color)
                if gained > 0:
                    zero_gain_streak = 0
                else:
                    zero_gain_streak += 1
                    if zero_gain_streak >= 2:
                        log_color("    ⚠ два подряд раунда без прироста, стоп по блоку", ANSI_YELLOW)
                        success = False
                        break
            if current >= args.target_valid:
                completed_blocks += 1
                log_color(f"✅ Блок {block_idx}: цель достигнута", ANSI_GREEN)
            else:
                failed_blocks += 1
                if success and rounds >= args.max_rounds_per_block:
                    log_color(f"⚠ Блок {block_idx}: достигнут лимит раундов ({current}/{args.target_valid})", ANSI_YELLOW)
                else:
                    log_color(f"✗ Блок {block_idx}: не добрали ({current}/{args.target_valid})", ANSI_RED)

    summary_color = ANSI_GREEN if failed_blocks == 0 else ANSI_YELLOW
    log_color(f"Итог: блоков={total_blocks}, успешно={completed_blocks}, проблемных={failed_blocks}", summary_color)
    if failed_blocks > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

