#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_TYPES = {"mcq_single"}

# В prompt/explanation не должны попадать внутренние имена полей/ключей (ученик их не видит).
_USER_FACING_BANNED_SUBSTRINGS = frozenset(
    {
        "common_mistakes",
        "key_points",
        "theory_block_id",
        "content_md",
        "chapter_id",
        "concept_id",
        "training_pack",
        "grammarbundle",
    }
)


def _forbidden_user_facing_leaks(text: str) -> list:
    if not str(text).strip():
        return []
    tl = str(text).lower()
    return sorted(s for s in _USER_FACING_BANNED_SUBSTRINGS if s in tl)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts}: {message}", flush=True)


ANSI_YELLOW = "\033[33m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_BOLD = "\033[1m"
ANSI_MAGENTA = "\033[35m"
ANSI_RESET = "\033[0m"


def log_yellow(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ANSI_YELLOW}{ts}: {message}{ANSI_RESET}", flush=True)


def log_cyan(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ANSI_CYAN}{ts}: {message}{ANSI_RESET}", flush=True)


def log_green(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ANSI_GREEN}{ts}: {message}{ANSI_RESET}", flush=True)


def log_red(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ANSI_RED}{ts}: {message}{ANSI_RESET}", flush=True)


def log_bold(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ANSI_BOLD}{ts}: {message}{ANSI_RESET}", flush=True)


def _compact_tail(text: str, limit: int = 50) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[-limit:]


def _stream_status(prefix: str, text: str):
    tail = _compact_tail(text, 50)
    msg = f"{prefix} получаем ответ... {len(text)} симв ... {tail}"
    sys.stdout.write("\r" + ANSI_CYAN + msg + ANSI_RESET)
    sys.stdout.flush()


def short_err(err: str, limit: int = 140) -> str:
    one_line = re.sub(r"\s+", " ", str(err)).strip()
    if len(one_line) <= limit:
        return one_line
    return one_line[:limit] + "..."


def load_generator_config(course_root: Path):
    cfg_path = course_root / "config" / "training-pack.json"
    if not cfg_path.exists():
        return {}
    try:
        return read_json(cfg_path)
    except Exception:
        return {}


def normalize_text(v):
    if v is None:
        return ""
    t = str(v).strip().lower()
    # Remove quote variants to avoid signature mismatch on typography only.
    t = re.sub(r"[\"'`´«»„“”‘’‚‛‹›]", "", t)
    return " ".join(t.split())


def has_cyrillic(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x0400 <= code <= 0x04FF:
            return True
    return False


def question_signature(q):
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
    # Fallback для совместимости: если choices/ответ нечитабельны,
    # используем исходное поле correct_answer.
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
    """
    Remove duplicate choices by normalized text.
    Priority: keep the correct-answer choice when duplicates conflict.
    Returns number of removed choices.
    """
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


def normalize_choice_ids_and_correct_answer(q: dict):
    choices = q.get("choices")
    if not isinstance(choices, list) or len(choices) < 2 or len(choices) > 4:
        return
    letters = ["a", "b", "c", "d"]
    old_ids = [c.get("id") if isinstance(c, dict) else None for c in choices]
    correct = q.get("correct_answer")
    correct_idx = None
    if correct in old_ids:
        correct_idx = old_ids.index(correct)
    elif normalize_text(correct):
        ncorrect = normalize_text(correct)
        for i, c in enumerate(choices):
            if isinstance(c, dict) and normalize_text(c.get("text", "")) == ncorrect:
                correct_idx = i
                break
    for i, c in enumerate(choices):
        if isinstance(c, dict):
            c["id"] = letters[i]
    if correct_idx is not None:
        q["correct_answer"] = letters[correct_idx]


def _count_comma_spelling_segments(choice_text: str) -> int:
    """
    Сегменты в ответе вида «eme, a, erre, te, a»; пустые после split отбрасываем.
    """
    if not str(choice_text).strip():
        return 0
    return len([p for p in re.split(r",\s*", str(choice_text).strip()) if p.strip()])


def _extract_word_for_full_letter_by_letter_spelling_prompt(prompt: str) -> Optional[str]:
    """
    Для вопросов вроде «произнести имя 'Marta' по буквам» — слово, которое должно
    проговариваться целиком; None если паттерн не тот.
    """
    t = str(prompt)
    m = re.search(
        r"(?:имя|слово)\s+[''«\`]([A-Za-záéíóúüñÁÉÍÓÚÜÑ]{2,})[''»\`]",
        t,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    if not re.search("по буквам", t, re.IGNORECASE):
        return None
    m = re.search(
        r"[''«\`]([A-Za-záéíóúüñÁÉÍÓÚÜÑ]{2,})[''»\`].{0,30}по буквам",
        t,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1)
    m = re.search(
        r"по буквам.{0,30}[''«\`]([A-Za-záéíóúüñÁÉÍÓÚÜÑ]{2,})[''»\`]",
        t,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1)
    return None


def validate_letter_by_letter_spelling_mcq(q: dict) -> list:
    """
    Цель: не пропускать варианты вроде «em, a, erre, a» для Marta (5 букв) —
    в правильном ответе должно быть столько сегментов, сколько букв в слове.
    """
    err = []
    prompt_text = str(q.get("prompt", ""))
    if "по буквам" not in prompt_text.lower():
        return err
    if re.search(
        r"втор\w* букв|трет\w* букв|перв\w* букв|как(ую|ой|ие)\s+букв|"
        r"как(ая|ое)\s+букв|букву\s+[''«\`]\s*([A-Za-záéíóúüñ])[''»\`]\s*в\s+",
        prompt_text,
        re.IGNORECASE,
    ):
        return err
    word = _extract_word_for_full_letter_by_letter_spelling_prompt(prompt_text)
    if not word:
        return err
    # ch/ll/rr: число сегментов в ответе может не совпадать с len(word) в зависимости от
    # методики; не штрафуем (ложные срабатывания). Marta-тип: без digraph-скипа.
    low = word.lower()
    for frag in ("ch", "ll", "rr"):
        if frag in low:
            return err
    ca = q.get("correct_answer")
    choices = q.get("choices")
    if not isinstance(choices, list) or not ca:
        return err
    correct_text = None
    for c in choices:
        if isinstance(c, dict) and c.get("id") == ca:
            correct_text = c.get("text", "")
            break
    if correct_text is None or str(correct_text).strip() == "":
        return err
    n_letters = len(word)
    n_segments = _count_comma_spelling_segments(str(correct_text))
    if n_segments != n_letters:
        err.append(
            f"для вопроса с полной расшифровкой по буквам ({word!r} = {n_letters} букв) в правильном варианте "
            f"ожидается ровно {n_letters} сегмент(а/ов) через запятую, сейчас {n_segments} — возможна пропущенная буква (например, te) или лишняя"
        )
    return err


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
    for idx, b in enumerate(chapter.get("blocks", []), start=1):
        if not isinstance(b, dict):
            continue
        if b.get("type") != "theory":
            continue
        bid = b.get("id")
        theory = b.get("theory", {}) if isinstance(b.get("theory"), dict) else {}
        if bid:
            out.append(
                {
                    "index": len(out) + 1,
                    "id": bid,
                    "chapter_id": chapter.get("id"),
                    "chapter_title": chapter.get("title", ""),
                    "chapter_level": chapter.get("level", ""),
                    "concept_id": theory.get("concept_id", ""),
                    "title": b.get("title", ""),
                    "content_md": theory.get("content_md", ""),
                    "key_points": theory.get("key_points", []),
                    "common_mistakes": theory.get("common_mistakes", []),
                    "examples": theory.get("examples", []),
                }
            )
    return out


def validate_question(q: dict, chapter_id: str, theory_block_ids: set):
    errors = []
    if q.get("type") not in SUPPORTED_TYPES:
        errors.append(f"unsupported type={q.get('type')}, only mcq_single is allowed")
    prompt_text = str(q.get("prompt", ""))
    explanation_text = str(q.get("explanation", ""))
    if not normalize_text(prompt_text):
        errors.append("empty prompt")
    elif not has_cyrillic(prompt_text):
        errors.append("prompt must contain Russian text (cyrillic)")
    for leak in _forbidden_user_facing_leaks(prompt_text):
        errors.append(f"prompt must not name internal data keys (found {leak!r}, not shown to learners)")
    if "correct_answer" not in q:
        errors.append("missing correct_answer")
    if not normalize_text(explanation_text):
        errors.append("missing explanation")
    elif not has_cyrillic(explanation_text):
        errors.append("explanation must contain Russian text (cyrillic)")
    for leak in _forbidden_user_facing_leaks(explanation_text):
        errors.append(
            f"explanation must not name internal data keys (found {leak!r}, not shown to learners)"
        )
    choices = q.get("choices")
    if not isinstance(choices, list) or len(choices) < 2:
        errors.append("mcq_single requires choices with at least 2 options")
    else:
        norm_choice_texts = []
        choice_ids = []
        for c in choices:
            if not isinstance(c, dict):
                errors.append("choice must be object")
                continue
            cid = c.get("id")
            ctext = c.get("text")
            if not normalize_text(cid):
                errors.append("choice missing id")
            if not normalize_text(ctext):
                errors.append("choice missing text")
            norm_choice_texts.append(normalize_text(ctext))
            choice_ids.append(cid)
        allowed_choice_ids = {"a", "b", "c", "d"}
        if len(choices) > 4:
            errors.append("mcq_single allows at most 4 choices")
        if len(set(choice_ids)) != len(choice_ids):
            errors.append("choice ids must be unique")
        if not set(choice_ids).issubset(allowed_choice_ids):
            errors.append("choice ids must be within a,b,c,d")
        if "correct_answer" in q and q.get("correct_answer") not in choice_ids:
            errors.append("correct_answer must reference choices[].id")
        elif "correct_answer" in q and q.get("correct_answer") not in allowed_choice_ids:
            errors.append("correct_answer must be one of a,b,c,d")
        if len(set(norm_choice_texts)) != len(norm_choice_texts):
            errors.append("duplicate choices by text are not allowed")
    block_id = q.get("theory_block_id")
    if not block_id:
        errors.append("missing theory_block_id")
    elif block_id not in theory_block_ids:
        errors.append(f"unknown theory_block_id={block_id}")
    if q.get("chapter_id") and q.get("chapter_id") != chapter_id:
        errors.append(f"chapter_id mismatch: {q.get('chapter_id')} != {chapter_id}")
    errors.extend(validate_letter_by_letter_spelling_mcq(q))
    return errors


def load_existing_pack(course_root: Path):
    pack_dir = course_root / "training_pack"
    idx_path = pack_dir / "index.json"
    if not idx_path.exists():
        return {"chapters": {}, "blocks": {}}, {}
    idx = read_json(idx_path)
    block_payloads = {}
    for block_key, rel in idx.get("blocks", {}).items():
        p = pack_dir / "chapters" / rel
        if p.exists():
            block_payloads[block_key] = read_json(p)
    return idx, block_payloads


def load_system_prompt(course_root: Path):
    prompt_path = course_root / "prompts" / "16-training-pack-generator-system.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return "Ты генератор mcq_single вопросов по испанской грамматике. Возвращай только JSON."


def build_prompt(system_prompt: str, spec: dict, count: int):
    return (
        f"{system_prompt}\n\n"
        "Ограничения:\n"
        "- Генерируй только type=mcq_single\n"
        "- Каждый вопрос обязан иметь choices: от 2 до 4 вариантов, каждый {id,text}\n"
        "- prompt и explanation пиши по-русски\n"
        "- text в choices пиши по-испански\n"
        "- Верни JSON массив объектов вопросов\n"
        f"- Сгенерируй ровно {count} вопросов\n\n"
        f"INPUT:\n{json.dumps(spec, ensure_ascii=False)}"
    )


def _openai_chat_generate(model: str, prompt: str, base_url: str):
    base = base_url.rstrip("/")
    api_key = os.environ.get("LOCAL_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    chat_body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "stream": True,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    chat_req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=chat_body,
        headers=headers,
        method="POST",
    )
    parts: List[str] = []
    with urllib.request.urlopen(chat_req, timeout=360) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                break
            try:
                data = json.loads(line)
            except Exception:
                continue
            choices = data.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            chunk = delta.get("content", "")
            if not chunk and isinstance(choices[0].get("message"), dict):
                chunk = choices[0]["message"].get("content", "")
            if chunk:
                parts.append(chunk)
                _stream_status("[LLM]", "".join(parts))
    if parts:
        sys.stdout.write("\n")
        sys.stdout.flush()
    return "".join(parts)


def llm_generate(model: str, prompt: str, base_url: str):
    base = base_url.rstrip("/")
    try:
        return _openai_chat_generate(model=model, prompt=prompt, base_url=base)
    except urllib.error.HTTPError as e:
        if e.code not in (404, 405):
            raise
    except Exception:
        pass
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.1},
            "keep_alive": "30m",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    parts: List[str] = []
    with urllib.request.urlopen(req, timeout=360) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            chunk = data.get("response", "")
            if chunk:
                parts.append(chunk)
                _stream_status("[LLM]", "".join(parts))
            if data.get("done") is True:
                break
    if parts:
        sys.stdout.write("\n")
        sys.stdout.flush()
    return "".join(parts)


def generate_for_block_llm(system_prompt: str, block: dict, count: int, model: str, base_url: str):
    log(f"  ↳ LLM запрос: нужно {count} шт.")
    prompt = build_prompt(system_prompt, block, count)
    print(f"{ANSI_MAGENTA}[LLM REQUEST][{block.get('chapter_id','')}::{block.get('id','')}] {prompt}{ANSI_RESET}", flush=True)
    try:
        raw = llm_generate(model=model, prompt=prompt, base_url=base_url)
    except Exception as e:
        return [], "", str(e)
    print(f"{ANSI_GREEN}[LLM RESPONSE][{block.get('chapter_id','')}::{block.get('id','')}] {raw}{ANSI_RESET}", flush=True)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            log(f"  ↳ LLM ответ: получено {len(parsed)} шт.")
            return parsed, raw, None
        return [], raw, "LLM response is not list"
    except Exception as e:
        return [], raw, str(e)


def parse_selection(chapters: List[dict], chapter_number: int, block_number: int):
    selected = []
    for ch in chapters:
        if chapter_number and ch.get("__index") != chapter_number:
            continue
        blocks = theory_blocks(ch)
        if block_number:
            blocks = [b for b in blocks if b["index"] == block_number]
        for b in blocks:
            selected.append((ch, b))
    return selected


def build_file_prefix(language: str, chapter_idx: int, block_idx: int) -> str:
    return f"{language}.{chapter_idx:03d}.{block_idx:03d}"


def block_key(chapter_id: str, block_id: str) -> str:
    return f"{chapter_id}::{block_id}"


def block_rel_path(language: str, chapter_idx: int, block_idx: int, block_id: str) -> str:
    # Requested format: chapters/001/es.02.code
    return f"{chapter_idx:03d}/{language}.{block_idx:02d}.{block_id}.questions.json"


def validate_pack(course_root: Path, min_per_block: int) -> Tuple[bool, dict]:
    pack_dir = course_root / "training_pack"
    report = {
        "generated_at": utc_now(),
        "ok": True,
        "errors": [],
        "chapters": {},
        "weak_blocks": [],
    }
    idx_path = pack_dir / "index.json"
    if not idx_path.exists():
        report["ok"] = False
        report["errors"].append("missing training_pack/index.json")
        return False, report
    idx = read_json(idx_path)
    global_signatures = set()
    block_counts: Dict[str, int] = {}
    chapters = {ch["id"]: ch for ch in load_chapters(course_root)}
    chapter_reports: Dict[str, dict] = {}
    for block_ref, rel_path in idx.get("blocks", {}).items():
        if "::" not in block_ref:
            continue
        chapter_id, block_id = block_ref.split("::", 1)
        chapter_report = chapter_reports.get(chapter_id, {"errors": [], "accepted_questions": 0, "duplicates_removed": 0})
        chapter = chapters.get(chapter_id)
        theory_ids = {b["id"] for b in theory_blocks(chapter)} if chapter else set()
        cp = pack_dir / "chapters" / rel_path
        if not cp.exists():
            chapter_report["errors"].append(f"missing chapter pack file: {cp.name}")
            report["ok"] = False
            chapter_reports[chapter_id] = chapter_report
            continue
        payload = read_json(cp)
        accepted = []
        seen_local = set()
        for q in payload.get("questions", []):
            errs = validate_question(q, chapter_id, theory_ids)
            sig = q.get("signature") or question_signature(q)
            if sig in seen_local or sig in global_signatures:
                chapter_report["duplicates_removed"] += 1
                continue
            if errs:
                chapter_report["errors"].append({"question_id": q.get("id", ""), "errors": errs})
                continue
            q["signature"] = sig
            seen_local.add(sig)
            global_signatures.add(sig)
            accepted.append(q)
            block_counts[q.get("theory_block_id")] = block_counts.get(q.get("theory_block_id"), 0) + 1
        # Validation is non-destructive: do not rewrite chapter files here.
        chapter_report["accepted_questions"] += len(accepted)
        chapter_report["duplicates_removed"] += max(0, len(payload.get("questions", [])) - len(accepted))
        if chapter_report["errors"]:
            report["ok"] = False
        chapter_reports[chapter_id] = chapter_report
    report["chapters"] = chapter_reports
    for block_id, count in sorted(block_counts.items()):
        if count < min_per_block:
            report["weak_blocks"].append({"theory_block_id": block_id, "count": count, "min_required": min_per_block})
    write_json(pack_dir / "reports" / "validation-report.json", report)
    return report["ok"], report


def renumber_question_ids(questions: List[dict]):
    idx = 1
    for q in questions:
        if not isinstance(q, dict):
            continue
        q["id"] = f"q{idx}"
        idx += 1


def build_pack(course_root: Path, min_per_block: int, questions_per_block: int, llm_model: str, llm_base_url: str, chapter_number: int, block_number: int, append: bool):
    system_prompt = load_system_prompt(course_root)
    pack_dir = course_root / "training_pack"
    pack_chapters_dir = pack_dir / "chapters"
    runs_dir = pack_dir / "runs" / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (pack_dir / "reports").mkdir(parents=True, exist_ok=True)
    pack_chapters_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    bundle_id = (course_root / "bundle.target").read_text(encoding="utf-8").strip()
    gen_cfg = load_generator_config(course_root)
    gen_version = gen_cfg.get("generator_version", "training-pack-generator-v3")
    prompt_version = gen_cfg.get("prompt_version", "sp-grammar-pack-v2-mcq-single")

    index, block_payloads = load_existing_pack(course_root) if append else ({"chapters": {}, "blocks": {}}, {})
    config = {
        "version": "1.0.0",
        "language": bundle_id,
        "course_id": course_root.name,
        "generated_at": utc_now(),
        "generator_version": gen_version,
        "mode": "llm-only",
        "prompt_version": prompt_version,
        "chapters": {},
        "blocks": dict(index.get("blocks", {})),
    }

    selected = parse_selection(load_chapters(course_root), chapter_number=chapter_number, block_number=block_number)
    if not selected:
        raise SystemExit("No target theory blocks found for selected filters")
    log_bold(f"▶ Старт генерации: блоков в работе = {len(selected)}")
    generated_blocks = 0

    for chapter, block in selected:
        chapter_id = chapter["id"]
        chapter_idx = int(chapter.get("__index", 0))
        block_idx = int(block.get("index", 0))
        log_bold(f"■ Глава {chapter.get('__index')}, блок {block.get('index')}: старт")
        bkey = block_key(chapter_id, block["id"])
        rel = block_rel_path(bundle_id, chapter_idx, block_idx, block["id"])
        existing_payload = block_payloads.get(
            bkey,
            {
                "chapter_id": chapter_id,
                "theory_block_id": block["id"],
                "course_version": chapter.get("schema_version", "1.0.0"),
                "questions": [],
                "meta": {},
            },
        )
        existing_questions = existing_payload.get("questions", [])
        # Auto-clean existing questions: drop duplicate choice texts with correct-answer priority.
        cleaned_existing = []
        dropped_existing = 0
        for exq in existing_questions:
            if not isinstance(exq, dict):
                dropped_existing += 1
                continue
            qq = dict(exq)
            dedupe_choice_texts_keep_correct(qq)
            choices = qq.get("choices")
            if not isinstance(choices, list) or len(choices) < 2 or len(choices) > 4:
                dropped_existing += 1
                continue
            ids = [c.get("id") for c in choices if isinstance(c, dict)]
            if len(ids) != len(choices) or len(set(ids)) != len(ids) or not set(ids).issubset({"a", "b", "c", "d"}):
                dropped_existing += 1
                continue
            if qq.get("correct_answer") not in ids:
                dropped_existing += 1
                continue
            cleaned_existing.append(qq)
        if dropped_existing > 0:
            log_yellow(f"  ⚠ удалено битых существующих вопросов: {dropped_existing}")
        existing_questions = cleaned_existing
        existing_sigs = {q.get("signature") or question_signature(q) for q in existing_questions if isinstance(q, dict)}

        accepted = []
        rejected_total = 0
        reject_reasons_questions: Dict[str, int] = {}
        zero_gain_streak = 0
        attempt = 0
        while len(accepted) < questions_per_block and zero_gain_streak < 2:
            attempt += 1
            remaining_needed = max(1, questions_per_block - len(accepted))
            log_cyan(f"  • Попытка {attempt}: нужно добавить {remaining_needed} (цель {questions_per_block})")
            llm_qs, raw_text, err = generate_for_block_llm(system_prompt, block, remaining_needed, llm_model, llm_base_url)
            raw_path = runs_dir / (
                f"{bundle_id}.{chapter_idx:03d}.{block_idx:03d}.{chapter_id}.{block['id']}.attempt{attempt:02d}.raw.json"
            )
            write_json(raw_path, {"attempt": attempt, "error": err, "raw_response": raw_text})
            log_cyan(f"    raw-log: {raw_path.name}")
            if err:
                log_yellow(f"    ✗ ошибка LLM на попытке {attempt}: {short_err(err)}")
                zero_gain_streak += 1
                continue

            accepted_before_attempt = len(accepted)
            rejected_attempt = 0
            for i, q in enumerate(llm_qs, start=1):
                if not isinstance(q, dict):
                    rejected_attempt += 1
                    reason = "payload item is not an object"
                    reject_reasons_questions[reason] = reject_reasons_questions.get(reason, 0) + 1
                    continue
                qq = dict(q)
                qq["type"] = "mcq_single"
                qq["theory_block_id"] = block["id"]
                qq["chapter_id"] = chapter_id
                qq["concept_id"] = qq.get("concept_id") or block.get("concept_id") or ""
                qq["difficulty"] = max(1, min(5, int(qq.get("difficulty", 2))))
                normalize_choice_ids_and_correct_answer(qq)
                removed_choice_dups = dedupe_choice_texts_keep_correct(qq)
                if removed_choice_dups > 0:
                    log_yellow(f"    ⚠ q#{i}: убраны дубли вариантов (-{removed_choice_dups})")
                if not qq.get("id"):
                    qq["id"] = f"{chapter_id}.{block['id']}.gen.{int(datetime.now().timestamp())}.{i:03d}"
                sig = question_signature(qq)
                qq["signature"] = sig
                if sig in existing_sigs:
                    rejected_attempt += 1
                    reason = "duplicate signature"
                    reject_reasons_questions[reason] = reject_reasons_questions.get(reason, 0) + 1
                    continue
                validation_errors = validate_question(qq, chapter_id, {block["id"]})
                if validation_errors:
                    rejected_attempt += 1
                    for reason in set(validation_errors):
                        reject_reasons_questions[reason] = reject_reasons_questions.get(reason, 0) + 1
                    continue
                accepted.append(qq)
                existing_sigs.add(sig)
                if len(accepted) >= questions_per_block:
                    break

            gained = len(accepted) - accepted_before_attempt
            rejected_total += rejected_attempt
            if gained > 0:
                zero_gain_streak = 0
            else:
                zero_gain_streak += 1
            mark = "✓" if gained > 0 else "·"
            log_cyan(f"    {mark} попытка {attempt}: +{gained}, всего {len(accepted)}, 0-подряд={zero_gain_streak}")

        if not append:
            existing_questions = []
        existing_questions.extend(accepted)
        renumber_question_ids(existing_questions)
        existing_payload["questions"] = existing_questions
        existing_payload["meta"] = {
            "generated_at": utc_now(),
            "source": "llm-only",
            "questions_per_block": questions_per_block,
            "chapter_number_filter": chapter_number or None,
            "block_number_filter": block_number or None,
            "append": append,
        }
        write_json(pack_chapters_dir / rel, existing_payload)
        config["blocks"][bkey] = rel
        config["chapters"].setdefault(chapter_id, [])
        if rel not in config["chapters"][chapter_id]:
            config["chapters"][chapter_id].append(rel)
        status_mark = "✅" if len(accepted) > 0 else "⚪"
        if len(accepted) > 0:
            log_green(f"{status_mark} Глава {chapter.get('__index')}, блок {block.get('index')}: добавлено {len(accepted)}, отклонено {rejected_total}, всего в файле {len(existing_questions)}")
        else:
            log_yellow(f"{status_mark} Глава {chapter.get('__index')}, блок {block.get('index')}: добавлено {len(accepted)}, отклонено {rejected_total}, всего в файле {len(existing_questions)}")
        if reject_reasons_questions:
            for reason, count in sorted(reject_reasons_questions.items(), key=lambda item: (-item[1], item[0])):
                log_yellow(f"    - {count} шт.: {reason}")
        if accepted:
            generated_blocks += 1

    if generated_blocks == 0:
        raise SystemExit("No questions were generated. Check training_pack/runs/*/*.raw.json and your LLM endpoint/model.")

    write_json(pack_dir / "index.json", config)
    ok, report = validate_pack(course_root=course_root, min_per_block=min_per_block)
    write_json(pack_dir / "reports" / "build-report.json", {"ok": ok, "generated_at": utc_now(), "mode": "llm-only", "validation": report})
    return ok, report


def main():
    parser = argparse.ArgumentParser(description="Build Spanish training pack with LLM only (mcq_single)")
    parser.add_argument("--course-root", default=".")
    parser.add_argument("--min-per-block", type=int, default=None)
    parser.add_argument("--questions-per-block", type=int, default=None, help="How many NEW questions to generate for each targeted block")
    parser.add_argument("--chapter-number", type=int, default=0, help="1-based chapter index in sorted chapters/ dirs")
    parser.add_argument("--block-number", type=int, default=0, help="1-based theory block index inside selected chapter")
    parser.add_argument("--append", action="store_true", help="Append new questions, do not replace targeted block questions")
    parser.add_argument("--llm-base-url", default=None, help="Base URL for llama.cpp/OpenAI-compatible or Ollama server")
    parser.add_argument("--ollama-url", default=None, help="Deprecated alias for --llm-base-url")
    parser.add_argument("--llm-model", default=None)
    args = parser.parse_args()

    course_root = Path(args.course_root).resolve()
    cfg = load_generator_config(course_root)
    defaults = cfg.get("defaults", {}) if isinstance(cfg.get("defaults", {}), dict) else {}
    min_per_block = args.min_per_block if args.min_per_block is not None else int(defaults.get("min_per_block", 3))
    questions_per_block = args.questions_per_block if args.questions_per_block is not None else int(defaults.get("questions_per_block", 3))
    llm_model = args.llm_model or os.environ.get("TRAINING_PACK_MODEL") or defaults.get("llm_model", "qwen2.5:14b-instruct")
    llm_base_url = (
        args.llm_base_url
        or args.ollama_url
        or os.environ.get("LLM_BASE_URL")
        or os.environ.get("OLLAMA_URL")
        or defaults.get("llm_base_url")
        or defaults.get("ollama_url")
        or "http://127.0.0.1:8090"
    )

    ok, report = build_pack(
        course_root=course_root,
        min_per_block=min_per_block,
        questions_per_block=questions_per_block,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        chapter_number=args.chapter_number,
        block_number=args.block_number,
        append=args.append,
    )
    weak = report.get("weak_blocks", [])
    if weak:
        log_yellow("⚠ Блоки ниже min-per-block:")
        for row in weak[:50]:
            log(f"  - {row['count']} < {row['min_required']}")
    if not ok:
        log_red("✗ Валидация не пройдена")
        chapter_errors = report.get("chapters", {}) if isinstance(report.get("chapters", {}), dict) else {}
        shown = 0
        for _, ch in chapter_errors.items():
            errs = ch.get("errors", []) if isinstance(ch, dict) else []
            for e in errs:
                if isinstance(e, str):
                    log_red(f"  - {e}")
                    shown += 1
                elif isinstance(e, dict):
                    qid = e.get("question_id") or "?"
                    reasons = e.get("errors", [])
                    if reasons:
                        log_red(f"  - q={qid}: {short_err('; '.join(str(r) for r in reasons), 220)}")
                        shown += 1
                if shown >= 10:
                    break
            if shown >= 10:
                break
        if shown == 0:
            log_red("  - Детали см. training_pack/reports/validation-report.json")
        raise SystemExit(2)
    log_green("✅ Готово: training_pack собран и провалидирован")


if __name__ == "__main__":
    main()

