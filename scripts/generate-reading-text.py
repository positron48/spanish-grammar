#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import time


LEVELS = {"A0", "A1", "A2", "B1", "B2", "C1"}


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


def _load_reading_llm_client():
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import reading_llm_client as rlm  # noqa: WPS433 — shared repo helper

    return rlm


def llm_generate(prompt: str, course_root: pathlib.Path, level: str = "A2") -> dict:
    rlm = _load_reading_llm_client()
    raw = rlm.chat_completion(prompt, course_root, level=level)
    try:
        return rlm.parse_reading_json_response(raw)
    except ValueError as e:
        preview = (raw or "")[:500].replace("\n", " ")
        raise SystemExit(f"{e}\n[reading] raw preview: {preview!r}") from e


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


def target_language_name(code: str) -> str:
    """Human-readable name so the LLM does not treat ISO codes as filler."""
    c = (code or "").strip().lower()
    return {"en": "English", "es": "Spanish"}.get(c, c.upper())


def _cefr_level_block(level: str, target_lang: str) -> str:
    """Mandatory CEFR constraints; must override creative direction when they conflict."""
    lv = level.upper()
    if lv == "A0" and target_lang == "es":
        return """
CEFR A0 Spanish (STRICT):
- Max **8 words** per `text` line; present only; no *porque/cuando/si/que* clauses — two short sentences instead.
- First-week vocabulary only (hola, hay, es, está, tengo, quiero, veo, agua, pan, playa, tienda, calor, hora, euro…).
- Forbidden: *cigüeña*, *símbolo*, *construir*, *tradición*, rare/technical words.
- One **познавательный** факт (культура/быт/география) в простых словах, встроенный в 2–3 реплики (напр. «La cena es tarde. Es a las nueve.»). **40–120** word tokens total; не пустой обмен приветствиями.
""".strip()
    if lv == "A0":
        return "CEFR A0: max 8 words/line, present only, basic words, one simple insight, 40–120 tokens total."
    if lv == "A1":
        return "CEFR A1: max 12 words/line, concrete daily life, 50–160 tokens total."
    return "CEFR B1+: natural vocabulary for level, 50–200 tokens total."


def _scenario_directions(target_lang: str, level: str) -> list[str]:
    """Random creative seeds so the model does not default to the same shop dialogue."""
    lv = level.upper()
    if target_lang == "es" and lv == "A0":
        return [
            "En la playa: bandera verde, buen baño.",
            "La cena es tarde: a las nueve.",
            "Hace calor: bebemos agua en el café.",
            "En la parada: el autobús es el número cinco.",
            "En el parque: hay sol y árboles.",
            "En la tienda: el pan cuesta dos euros.",
            "Por la mañana: el desayuno es a las ocho.",
            "Hoy hay lluvia: tengo un paraguas.",
            "En la escuela: la clase es a las diez.",
            "En la playa: el mar es azul.",
            "La tienda cierra a las dos.",
        ]
    if target_lang == "es":
        common = [
            "Friends at a bus stop: one explains that many Spanish cities still post paper timetables at the stop.",
            "Neighbors on a terrace talk about why so many homes have small balconies (climate and lifestyle).",
            "At the beach: they notice colored flags and explain what green/yellow/red mean for swimming safety.",
            "Calling a museum: free entry on Sunday afternoons is common in many Spanish cities (one practical fact).",
            "Planning to watch fútbol: mention that evening matches in Spain often start late (cultural habit).",
            "At the pharmacy: the green cross sign and that some medicines are behind the counter.",
            "Metro ride: rechargeable travel card instead of buying a paper ticket each time.",
            "Summer heat: compare coastal humidity vs inland dry heat — one short geography fact.",
            "Weekend market: tropical fruit names plus the fact that Spain imports a lot of avocado and banana.",
            "Library visit: public libraries often offer free Wi‑Fi and quiet study rooms.",
            "Train platform: AVE fast train vs regional — one sentence on speed difference.",
            "Birthday chat: turrón as a typical winter sweet around Christmas.",
            "Park jog: olive trees are common in southern city parks (why: Mediterranean flora).",
            "Cooking at home: gazpacho is a cold tomato soup for hot days.",
            "Recycling area: colored bins for paper/plastic/glass — quick sorting rule.",
            "Siesta talk: many shops close mid‑afternoon and reopen (not a lecture — one line in dialogue).",
            "Phone abroad: country code +34 when dialing Spain.",
        ]
        if lv == "A1":
            return common + [
                "Lost room key at a small hostal — reception helps and mentions 24h desk in many hostales.",
                "Choosing between churros or tostada for breakfast — one food tradition fact.",
                "Asking why dinner is late (around 9–10 p.m.) in Spain — one cultural timing fact.",
                "Bird on the church roof: local good-luck custom — A1 vocabulary only (no rare species names).",
            ]
        return common + [
            "Stargazing: less light pollution in rural pueblos than in big city centers.",
            "Fountain in the plaza: many historic centers reuse old water channels (light history).",
            "Debate: tapas as sharing culture vs ración for one person — one etiquette fact.",
            "Election poster in the street: voting age 18 and Sunday voting tradition (neutral, factual).",
        ]
    # English course seeds
    common_en = [
        "Commuters discuss why UK trains use platform screens but some rural stations still have paper boards.",
        "Roommates compare Fahrenheit vs Celsius weather apps — one short science fact.",
        "At a bookshop: Shakespeare is staged often in small UK theatres (cultural fact).",
        "Tea break: milk-in-first vs tea-first as a light British culture debate.",
        "Park ducks: feeding bread is discouraged — why (wildlife fact).",
        "Bus delay: contactless card tap on London buses (transport fact).",
        "Museum: free national museums in London (practical fact).",
        "Football chat: extra time and penalties rules in simple terms.",
        "Rainy day: why umbrellas are common but locals still say 'only a shower'.",
        "Supermarket labels: best-before vs use-by (food safety fact).",
    ]
    return common_en


def build_prompt(
    level: str,
    fmt: str,
    target_lang: str,
    title: str,
    avoid_titles: list[str] | None = None,
):
    lang_name = target_language_name(target_lang)
    if title:
        title_line = f"Escena: {title}"
    else:
        seed = random.choice(_scenario_directions(target_lang, level))
        title_line = f"Escena (síguela): {seed}"
    speaker_rules = (
        "- Use ONLY narrator as speaker_id for all segments."
        if fmt == "narrative"
        else "- Use ONLY speaker_a and speaker_b as speaker_id (no narrator segments)."
    )
    avoid_block = ""
    if avoid_titles:
        shown = avoid_titles[:6]
        extra = len(avoid_titles) - len(shown)
        lines = ", ".join(shown)
        more = f" (+{extra} more)" if extra > 0 else ""
        avoid_block = f"Already used titles (do not repeat): {lines}{more}. Pick a new scene and title_short.\n"

    level_block = _cefr_level_block(level, target_lang)

    coherence = """
One coherent mini-dialogue or narration; logical order; one greeting max; closed ending.
Follow the CEFR block for vocabulary and length. No generic shop-only scenes or vague titles like «En la tienda».
**Обязательно:** один конкретный познавательный факт (культура, быт, транспорт, география, еда) — вплетите в реплики на {lang_name}, не отдельной лекцией.
Минимум **6** сегментов с непустым `text`; пустые реплики и «только hola/adiós» недопустимы.
Каждый сегмент должен нести смысл: обычно 5+ слов (кроме одного короткого приветствия/прощания).
Перед финальным JSON проверьте суммарную длину `segments[].text`: для A0 минимум 40 слов, для A1 минимум 50 слов; если меньше — добавьте содержательные реплики.
Один вопрос в `questions` проверяет этот факт; остальные — по сюжету.
6–10 segments; `text_translation_ru` in Russian.
""".strip()
    return f"""
/no_think
Верните **только** один JSON-объект. Первый символ ответа — `{{`.
Запрещено: английский план, рассуждения, markdown, текст вне JSON.
Generate one reading text for language learners: target language is **{lang_name}** (ISO code `{target_lang}`), CEFR level {level}, format {fmt}.
{title_line}
{avoid_block}

{level_block}

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
- Language (critical): The learner studies **{lang_name}**. Every segment's field `text` MUST be written 100% in **{lang_name}** only.
  When `{target_lang}` is `es`, do NOT write dialogue or narration in English. When `{target_lang}` is `en`, do NOT use Spanish for `text`.
  Mixed-language `text` (e.g. English lines for a Spanish course) is invalid.
- `title_short` must be in **{lang_name}**. `text_translation_ru` remains Russian (translation for Russian-speaking learners).
- `vocab_focus` words must appear in the passage and be spelled as in **{lang_name}**.
- 6–12 segments when needed; total `text` length must match the CEFR block for {level}.
- Hard minimum by level: A0 => >=40 word tokens, A1 => >=50, A2+ => >=50.
- Stay on one main topic aligned with title_hint or the creative direction (simplified for A0 if needed).
- questions 3-8 items; at least one question must target the insight fact; others on plot/details from segments.
- In dialogues, set speaker_gender for every segment (female/male/neutral).
- Use 2 recurring speakers in dialogue mode; lines must reply to each other and stay on one conversation thread.
- Keep speaker_gender consistent for the same speaker_id.
- Final segment must complete the piece: for dialogue, the last line closes the exchange (no unanswered question as the final segment); for narrative, close the scene without an abrupt cut.
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

    _scripts_dir = pathlib.Path(__file__).resolve().parent
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    import reading_catalog_maintain as rcm

    pruned = rcm.prune_reading_catalog(course_root, args.draft_dir, min_words=40, dry_run=False)
    print(f"[reading] catalog prune at startup: removed {len(pruned)} text(s)")

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
        json_level = str(generated.get("level", "")).upper().strip()
        if json_level in LEVELS:
            level = json_level
    else:
        avoid_titles = rcm.existing_display_titles(course_root, args.draft_dir, limit=6)
        prompt = build_prompt(
            level, args.format, args.target_lang, args.title, avoid_titles=avoid_titles
        )
        generated = llm_generate(prompt, course_root, level=level)

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
        segments.append(
            {
                "segment_id": seg.get("segment_id") or f"seg_{i:02d}",
                "speaker_id": speaker_id,
                "voice_id": voice_id,
                "text": text,
                "text_translation_ru": seg.get("text_translation_ru", ""),
                "audio_rel_path": audio_rel,
                "_raw_index": i,
            }
        )
    if not segments:
        raise SystemExit("no segments generated")

    wc = rcm.word_count_from_generated_segments({"segments": [{"text": s["text"]} for s in segments]})
    if not input_json and wc < 40:
        raise SystemExit(f"generated text too short: {wc} word tokens (minimum 40)")

    title_new = str(generated.get("title_short") or args.title or "Reading Text").strip()
    if chapter_file is None:
        if rcm.normalize_title(title_new) in rcm.existing_normalized_titles(course_root, args.draft_dir):
            raise SystemExit(f"duplicate title in catalog: {title_new!r} — not saving")

    for s in segments:
        audio_abs = course_root / s["audio_rel_path"]
        ensure_audio(audio_abs, s["text"], s["voice_id"], tts_cmd_template)
        s["tokens"] = tokenize(s["text"])
        del s["_raw_index"]

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
