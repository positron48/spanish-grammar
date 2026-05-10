#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request


LEVELS = {"A0", "A1", "A2", "B1", "B2", "C1"}


def extract_json_block(raw: str) -> str:
    raw = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, flags=re.S)
    if fenced:
        return fenced.group(1)
    return raw


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", (value or "").strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "reading"


def upsert_reading_catalog(
    course_root: pathlib.Path,
    output_root: str,
    text_id: str,
    category_id: str,
    level: str,
    target_lang: str,
    title: str,
    reading_block: dict,
) -> pathlib.Path:
    reading_root = course_root / output_root
    texts_dir = reading_root / "texts"
    texts_dir.mkdir(parents=True, exist_ok=True)

    text_doc = {
        "id": text_id,
        "category_id": category_id,
        "title": title,
        "level": level,
        "target_language": target_lang,
        "reading_passage": reading_block.get("reading_passage", {}),
    }
    text_path = texts_dir / f"{text_id}.json"
    with open(text_path, "w", encoding="utf-8") as f:
        json.dump(text_doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    index_path = reading_root / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {
            "version": "1.0.0",
            "generated_at": "",
            "categories": {},
            "texts": {},
        }

    categories = index.setdefault("categories", {})
    cat = categories.get(category_id) or {
        "id": category_id,
        "title": f"{target_lang.upper()} {level} Reading",
        "level": level,
        "order": 0,
        "text_ids": [],
    }
    text_ids = cat.get("text_ids", [])
    if text_id not in text_ids:
        text_ids.append(text_id)
    cat["text_ids"] = text_ids
    categories[category_id] = cat

    texts_map = index.setdefault("texts", {})
    texts_map[text_id] = f"texts/{text_id}.json"
    index["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return text_path


def tokenize(text: str):
    parts = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    tokens = []
    idx = 0
    for part in parts:
        is_word = re.match(r"^\w+$", part) is not None
        tokens.append(
            {
                "surface": part,
                "lemma": part.lower() if is_word else part,
                "clickable": is_word,
                "token_idx": idx,
            }
        )
        idx += 1
    return tokens


def openai_chat_completions_url(ai_url: str) -> str:
    """Build POST URL for OpenAI-compatible providers.

    Accepts AI_URL as either:
    - https://openrouter.ai/api/v1  → …/api/v1/chat/completions
    - http://host:11434            → …/v1/chat/completions (Ollama / llama.cpp)
    """
    base = ai_url.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if re.search(r"/v\d+$", base):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def llm_generate(prompt: str) -> dict:
    ai_url = os.getenv("AI_URL", "").strip()
    api_key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "gpt-4o-mini").strip()
    if not ai_url or not api_key:
        raise RuntimeError("AI_URL/AI_API_KEY are required for generation")

    chat_url = openai_chat_completions_url(ai_url)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
    }
    req = urllib.request.Request(
        chat_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        raise RuntimeError(
            f"LLM HTTP {e.code} for {chat_url} "
            f"(check AI_URL; Ollama needs host or host:port, script adds /v1). Body: {detail}"
        ) from e
    content = body["choices"][0]["message"]["content"]
    return json.loads(extract_json_block(content))


def ensure_audio(audio_path: pathlib.Path, text: str, voice_id: str, tts_cmd_template: str):
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    if tts_cmd_template:
        cmd = (
            tts_cmd_template.replace("{text}", text.replace('"', '\\"'))
            .replace("{voice_id}", voice_id)
            .replace("{output}", str(audio_path))
        )
        subprocess.run(cmd, shell=True, check=True)
        return
    if not audio_path.exists():
        audio_path.write_bytes(b"")


def build_prompt(level: str, fmt: str, target_lang: str, title: str):
    title_line = f"title_hint: {title}" if title else "title_hint: auto"
    speaker_rules = (
        "- Use ONLY narrator as speaker_id for all segments."
        if fmt == "narrative"
        else "- Use ONLY speaker_a and speaker_b as speaker_id (no narrator segments)."
    )
    coherence = """
Coherence (mandatory — this is reading, not a phrasebook drill):
- Produce ONE coherent mini-text: a tiny story or one clear scene/situation. Every segment must follow logically from the previous (time, cause→effect, question→answer, reaction).
- The full sequence s1→s2→… must read as continuous discourse when concatenated (same persons, place, and topic unless one clear scene change you name).
- Do NOT output a list of unrelated sentences, pattern drills, or disconnected grammar examples. Avoid repetition of the same idea in adjacent segments unless it advances the situation.
- At A0–A1 you still need a thread: e.g. meeting someone, one simple problem + feeling, greeting + small plan — not random isolated lines.
""".strip()
    return f"""
Return JSON only.
Generate one {target_lang} reading text for level {level}, format {fmt}.
{title_line}
{coherence}
Schema:
{{
  "title_short": "string",
  "level": "{level}",
  "segments": [
    {{"segment_id":"s1","speaker_id":"narrator|speaker_a|speaker_b","speaker_gender":"neutral|female|male","text":"...","text_translation_ru":"..."}}
  ],
  "vocab_focus": ["word1","word2"],
  "questions": [{{"id":"q1","prompt":"...","type":"true_false","correct_answer":"true","explanation":"..."}}]
}}
Constraints:
- 4-8 segments (prefer at least 4 so the story can develop).
- Keep sentences short and natural for {level}; stay on one main topic aligned with title_hint.
- questions 3-8 items; base them on facts/events that appear in the segments.
- In dialogues, set speaker_gender for every segment (female/male/neutral).
- Use 2 recurring speakers in dialogue mode; lines must reply to each other and stay on one conversation thread.
- Keep speaker_gender consistent for the same speaker_id.
{speaker_rules}
""".strip()


def _norm_gender(value: str) -> str:
    v = (value or "").strip().lower()
    if v in {"m", "male", "man", "masculine"}:
        return "male"
    if v in {"f", "female", "woman", "feminine"}:
        return "female"
    return "neutral"


def resolve_voice_id(
    speakers_map: dict,
    voice_pool: dict,
    speaker_voice_cache: dict,
    speaker_id: str,
    speaker_gender: str,
    segment_idx: int,
) -> str:
    if speaker_id in speaker_voice_cache:
        return speaker_voice_cache[speaker_id]

    # Explicit speaker mapping has top priority.
    if speaker_id in speakers_map:
        voice_id = speakers_map[speaker_id]
        speaker_voice_cache[speaker_id] = voice_id
        return voice_id

    gender = _norm_gender(speaker_gender)
    gender_pool = voice_pool.get(gender, [])
    if gender_pool:
        voice_id = gender_pool[segment_idx % len(gender_pool)]
        speaker_voice_cache[speaker_id] = voice_id
        return voice_id

    narrator_voice = speakers_map.get("narrator")
    if narrator_voice:
        speaker_voice_cache[speaker_id] = narrator_voice
        return narrator_voice

    all_voice_ids = []
    for pool in voice_pool.values():
        all_voice_ids.extend(pool)
    if all_voice_ids:
        voice_id = all_voice_ids[segment_idx % len(all_voice_ids)]
        speaker_voice_cache[speaker_id] = voice_id
        return voice_id

    raise RuntimeError("voices profile does not define any usable voices")


def filter_existing_voice_ids(voice_ids, voice_dir: pathlib.Path):
    if not voice_dir:
        return list(voice_ids)
    kept = []
    for vid in voice_ids:
        onnx = voice_dir / f"{vid}.onnx"
        meta = voice_dir / f"{vid}.onnx.json"
        if onnx.exists() and meta.exists():
            kept.append(vid)
        else:
            print(
                f"[reading-generate-one] skip missing voice '{vid}' in {voice_dir}",
                file=sys.stderr,
            )
    return kept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter-id", default="")
    parser.add_argument("--course-root", default=".")
    parser.add_argument("--draft-dir", default="reading")
    parser.add_argument("--level", required=True)
    parser.add_argument("--format", choices=["narrative", "dialogue"], default="dialogue")
    parser.add_argument("--target-lang", choices=["en", "es"], required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--voices-profile", default="config/reading-voices.json")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--tts-cmd-template", default="")
    parser.add_argument("--input-json", default="")
    args = parser.parse_args()

    level = args.level.upper()
    if level not in LEVELS:
        raise SystemExit("level must be one of A0..C1")

    course_root = pathlib.Path(args.course_root).resolve()
    chapter_file = None
    chapter_id = args.chapter_id.strip()
    if chapter_id:
        for d in (course_root / "chapters").glob(f"*{chapter_id}*"):
            candidate = d / "05-final.json"
            if candidate.exists():
                chapter_file = candidate
                break
        if chapter_file is None:
            raise SystemExit(f"chapter not found: {chapter_id}")
    else:
        title_part = slugify(args.title)
        chapter_id = f"free_{args.target_lang}_{level.lower()}_{title_part}_{int(time.time())}"

    with open(course_root / args.voices_profile, "r", encoding="utf-8") as f:
        voices_profile = json.load(f)
    if args.target_lang not in voices_profile:
        raise SystemExit(f"voices profile has no language: {args.target_lang}")
    lang_profile = voices_profile[args.target_lang]
    speakers = lang_profile.get("speakers", {})
    voice_pool = {
        "male": list(lang_profile.get("male_voice_ids", [])),
        "female": list(lang_profile.get("female_voice_ids", [])),
        "neutral": list(lang_profile.get("neutral_voice_ids", [])),
    }
    voice_dir_env = os.getenv("READING_VOICE_DIR", "").strip()
    voice_dir = pathlib.Path(voice_dir_env) if voice_dir_env else None
    if voice_dir:
        for key in ("male", "female", "neutral"):
            voice_pool[key] = filter_existing_voice_ids(voice_pool[key], voice_dir)
    if not any(voice_pool.values()) and speakers:
        # Backward-compatible fallback for old profiles.
        voice_pool["neutral"] = list(dict.fromkeys(speakers.values()))
    if not any(voice_pool.values()):
        raise SystemExit("voices profile must contain male/female/neutral voice pools or speakers map")

    input_json = args.input_json or os.getenv("READING_INPUT_JSON", "").strip()
    tts_cmd_template = args.tts_cmd_template or os.getenv("READING_TTS_CMD_TEMPLATE", "").strip()

    if input_json:
        with open(input_json, "r", encoding="utf-8") as f:
            generated = json.load(f)
    else:
        generated = llm_generate(build_prompt(level, args.format, args.target_lang, args.title))

    segments = []
    speaker_voice_cache = {}
    for i, seg in enumerate(generated.get("segments", []), start=1):
        speaker_id = seg.get("speaker_id") or ("speaker_a" if i % 2 == 0 else "speaker_b")
        if args.format == "dialogue" and speaker_id == "narrator":
            speaker_id = "speaker_a"
        if args.format == "narrative":
            speaker_id = "narrator"
        speaker_gender = _norm_gender(seg.get("speaker_gender", "neutral"))
        voice_id = resolve_voice_id(speakers, voice_pool, speaker_voice_cache, speaker_id, speaker_gender, i - 1)
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        audio_rel = f"assets/reading/{chapter_id}/seg_{i:02d}_{speaker_id}.mp3"
        audio_abs = course_root / audio_rel
        ensure_audio(audio_abs, text, voice_id, tts_cmd_template)
        segments.append(
            {
                "segment_id": seg.get("segment_id") or f"seg_{i:02d}",
                "speaker_id": speaker_id,
                "voice_id": voice_id,
                "text": text,
                "text_translation_ru": seg.get("text_translation_ru", ""),
                "audio_rel_path": audio_rel,
                "tokens": tokenize(text),
            }
        )
    if not segments:
        raise SystemExit("no segments generated")

    reading_block = {
        "id": "reading_passage_auto",
        "type": "reading_passage",
        "title": generated.get("title_short") or args.title or "Reading Text",
        "reading_passage": {
            "title": generated.get("title_short") or args.title or "Reading Text",
            "level": level,
            "target_language": args.target_lang,
            "estimated_minutes": 6,
            "segments": segments,
            "vocab_focus": generated.get("vocab_focus", [])[:12],
            "comprehension_questions": generated.get("questions", [])[:8],
        },
    }

    output_path = ""
    if chapter_file is not None:
        with open(chapter_file, "r", encoding="utf-8") as f:
            chapter = json.load(f)
        blocks = [b for b in chapter.get("blocks", []) if b.get("type") != "reading_passage"]
        blocks.append(reading_block)
        chapter["blocks"] = blocks

        if not args.overwrite and any(b.get("type") == "reading_passage" for b in chapter.get("blocks", [])[:-1]):
            raise SystemExit("reading_passage already exists (use --overwrite)")

        with open(chapter_file, "w", encoding="utf-8") as f:
            json.dump(chapter, f, ensure_ascii=False, indent=2)
            f.write("\n")
        output_path = str(chapter_file)
    else:
        title = reading_block.get("reading_passage", {}).get("title") or reading_block.get("title") or "Reading Text"
        category_id = f"{args.target_lang}_{level.lower()}"
        text_path = upsert_reading_catalog(
            course_root=course_root,
            output_root=args.draft_dir,
            text_id=chapter_id,
            category_id=category_id,
            level=level,
            target_lang=args.target_lang,
            title=title,
            reading_block=reading_block,
        )
        output_path = str(text_path)

    report = {
        "text_id": chapter_id,
        "target_lang": args.target_lang,
        "level": level,
        "segments": len(segments),
        "audio_files": [s["audio_rel_path"] for s in segments],
        "output_path": output_path,
    }
    report_path = course_root / "reports" / "reading-build-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"reading generated: {output_path}")


if __name__ == "__main__":
    main()

