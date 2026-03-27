#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
SECTIONS_FILE = ROOT / "01-sections.md"
STATUS_FILE = ROOT / "config" / "generation-status.json"
TEMPLATES_DIR = ROOT / "config" / "chapter-templates"
COURSE_PREFIX = "es.grammar"
UI_LANGUAGE = "ru"
TARGET_LANGUAGE = "es"
VERSION = "1.0.0"
LEGACY_RESERVED_PREFIXES = 0  # No legacy reserved prefixes; generated chapter directories start at 001.*

SECTION_RE = re.compile(r"^### Section (\d+)\. (.+) \(([A-Za-z0-9-]+)\)$")
CHAPTER_RE = re.compile(r"^(\d+)\.(\d+)\. (.+)$")

SECTION_SLUGS = {
    0: "orientation_alphabet_sounds",
    1: "noun_gender_articles_agreement",
    2: "first_sentences_ser_pronouns",
    3: "existence_location_possession",
    4: "present_regular_actions",
    5: "present_irregulars_reflexives_gustar",
    6: "past_preterito_perfecto",
    7: "past_preterito_indefinido",
    8: "past_imperfecto_contrast",
    9: "future_conditionals",
    10: "obligation_ability_commands",
    11: "noun_phrase_upgrade_precision",
    12: "prepositions_verb_patterns",
    13: "pronouns_direct_indirect",
    14: "se_system_pronominal_verbs",
    15: "complex_sentences_connecting",
    16: "non_finite_forms_periphrases",
    17: "compound_tenses_narration",
    18: "subjunctive_noun_clauses",
    19: "subjunctive_time_purpose_relative",
    20: "subjunctive_past_counterfactuals",
    21: "voice_reported_speech_distancing",
    22: "c1_style_discourse_register",
}

SECTION_RU_TITLES = {
    0: "Ориентация: алфавит, звуки, ударение, пунктуация",
    1: "Первые строительные блоки: существительные, род, артикли, согласование",
    2: "Первые предложения: ser, местоимения, вопросы, отрицание",
    3: "Существование, местоположение и обладание: estar, hay, tener",
    4: "Настоящее 1: правильные глаголы и повседневные действия",
    5: "Настоящее 2: неправильные глаголы, чередования, возвратные формы, gustar",
    6: "Прошедшее 1: preterito perfecto и недавний опыт",
    7: "Прошедшее 2: preterito indefinido для завершенных действий",
    8: "Прошедшее 3: imperfecto и контраст прошедших времен",
    9: "Будущее и условное наклонение: планы, прогнозы, гипотезы",
    10: "Обязанность, способность и базовые команды",
    11: "Углубление именной группы: количество, сравнение, точность",
    12: "Предлоги и глагольные модели",
    13: "Местоимения 1: прямое и косвенное дополнение",
    14: "Местоимения 2 и система se",
    15: "Сложные предложения 1: как ясно связывать идеи",
    16: "Неличные формы и глагольные перифразы",
    17: "Сложные времена и улучшенная наррация",
    18: "Subjuntivo 1: presente de subjuntivo в изъяснительных придаточных",
    19: "Subjuntivo 2: время, цель, условие, относительные придаточные",
    20: "Subjuntivo 3: прошедшее subjuntivo и контрфактуальность",
    21: "Залог, косвенная речь и дистанцирование",
    22: "Стиль C1: дискурс, регистр, эмфаза, точность",
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "how", "in",
    "into", "is", "it", "more", "not", "of", "on", "one", "or", "the", "to",
    "vs", "what", "when", "with", "without",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")
@dataclass
class ChapterDef:
    section_number: int
    chapter_number: int
    title: str


@dataclass
class SectionDef:
    number: int
    title: str
    level_label: str
    level: str
    chapters: List[ChapterDef]


def parse_level(level_label: str) -> str:
    if "-" in level_label:
        return level_label.split("-")[-1]
    return level_label


def normalize_title(text: str) -> str:
    text = text.replace("&", " and ")
    text = text.replace("+", " plus ")
    text = text.replace("/", " ")
    text = text.replace("...", " ")
    return text.lower()


def slugify_title(title: str, *, keep_stopwords: bool = False, max_tokens: int = 8) -> str:
    raw_tokens = TOKEN_RE.findall(normalize_title(title))
    if keep_stopwords:
        tokens = raw_tokens
    else:
        tokens = [token for token in raw_tokens if token not in STOPWORDS]
        if not tokens:
            tokens = raw_tokens
    if title.lower().startswith("build"):
        max_tokens = max(max_tokens, 8)
    return "_".join(tokens[:max_tokens])


def title_short(title: str) -> str:
    if len(title) <= 60:
        return title
    if ":" in title:
        head, tail = title.split(":", 1)
        candidate = tail.strip()
        if candidate and len(candidate) <= 60:
            return candidate
        if len(head.strip()) <= 60:
            return head.strip()
    return title[:57].rstrip() + "..."


def parse_sections() -> List[SectionDef]:
    lines = SECTIONS_FILE.read_text(encoding="utf-8").splitlines()
    sections: List[SectionDef] = []
    current: SectionDef | None = None
    for line in lines:
        line = line.rstrip()
        m_section = SECTION_RE.match(line)
        if m_section:
            if current is not None:
                sections.append(current)
            number = int(m_section.group(1))
            title = m_section.group(2)
            level_label = m_section.group(3)
            current = SectionDef(
                number=number,
                title=title,
                level_label=level_label,
                level=parse_level(level_label),
                chapters=[],
            )
            continue
        m_chapter = CHAPTER_RE.match(line)
        if m_chapter and current is not None:
            sec_num = int(m_chapter.group(1))
            if sec_num != current.number:
                raise ValueError(f"Section/chapter mismatch: section {current.number}, chapter line {line}")
            current.chapters.append(
                ChapterDef(
                    section_number=sec_num,
                    chapter_number=int(m_chapter.group(2)),
                    title=m_chapter.group(3),
                )
            )
    if current is not None:
        sections.append(current)
    if not sections:
        raise ValueError(f"No sections parsed from {SECTIONS_FILE}")
    return sections


def chapter_slug(title: str, seen: set[str]) -> str:
    slug = slugify_title(title, max_tokens=8)
    if slug in seen:
        full = slugify_title(title, keep_stopwords=True, max_tokens=12)
        if full and full not in seen:
            slug = full
    if slug in seen:
        counter = 2
        base = slug
        while f"{base}_{counter}" in seen:
            counter += 1
        slug = f"{base}_{counter}"
    seen.add(slug)
    return slug


def build_status(sections: List[SectionDef]) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    section_entries = []
    chapter_entries = []
    global_index = 1
    output_prefix = LEGACY_RESERVED_PREFIXES + 1

    previous_section_last_chapter_id = None

    for section in sections:
        section_slug = SECTION_SLUGS[section.number]
        section_id = f"{COURSE_PREFIX}.{section_slug}"
        seen_slugs: set[str] = set()
        chapter_ids: List[str] = []
        chapter_defs = []

        for chapter in section.chapters:
            c_slug = chapter_slug(chapter.title, seen_slugs)
            chapter_id = f"{section_id}.{c_slug}"
            chapter_ids.append(chapter_id)
            chapter_defs.append((chapter, chapter_id))

        section_entries.append(
            {
                "section_id": section_id,
                "title": section.title,
                "level": section.level,
                "order": section.number,
                "chapter_ids": chapter_ids,
                "title_translations": {
                    "ru": SECTION_RU_TITLES[section.number],
                },
            }
        )

        for idx, (chapter, chapter_id) in enumerate(chapter_defs):
            if idx == 0:
                prerequisites = [previous_section_last_chapter_id] if previous_section_last_chapter_id else []
            else:
                prerequisites = [chapter_defs[idx - 1][1]]

            output_dir = f"chapters/{output_prefix:03d}.{chapter_id}"
            chapter_entries.append(
                {
                    "chapter_id": chapter_id,
                    "section_id": section_id,
                    "title": chapter.title,
                    "level": section.level,
                    "order": global_index,
                    "status": "pending",
                    "input_file": f"config/chapter-templates/{chapter_id}-input.json",
                    "output_dir": output_dir,
                    "files": {
                        "outline": f"{output_dir}/01-outline.json",
                        "theory_blocks": f"{output_dir}/02-theory-blocks/",
                        "questions": f"{output_dir}/03-questions.json",
                        "inline_quizzes": f"{output_dir}/04-inline-quizzes.json",
                        "final": f"{output_dir}/05-final.json",
                        "validation": f"{output_dir}/05-validation.json",
                    },
                    "prerequisites": prerequisites,
                }
            )
            global_index += 1
            output_prefix += 1

        previous_section_last_chapter_id = chapter_defs[-1][1] if chapter_defs else previous_section_last_chapter_id

    summary = {
        "total_sections": len(section_entries),
        "total_chapters": len(chapter_entries),
        "chapters_generated": 0,
        "chapters_in_progress": 0,
        "chapters_pending": len(chapter_entries),
        "chapters_failed": 0,
        "chapters_validated": 0,
        "last_updated": now,
    }

    return {
        "version": VERSION,
        "last_updated": now,
        "sections": section_entries,
        "chapters": chapter_entries,
        "summary": summary,
    }


def write_templates(status: dict) -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for chapter in status["chapters"]:
        template = {
            "chapter_input": {
                "section_id": chapter["section_id"],
                "chapter_id": chapter["chapter_id"],
                "title": chapter["title"],
                "title_short": title_short(chapter["title"]),
                "level": chapter["level"],
                "order": chapter["order"],
                "ui_language": UI_LANGUAGE,
                "target_language": TARGET_LANGUAGE,
                "prerequisites": chapter.get("prerequisites", []),
            }
        }
        template_path = TEMPLATES_DIR / f"{chapter['chapter_id']}-input.json"
        template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    sections = parse_sections()
    status = build_status(sections)
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_templates(status)
    print(f"Wrote {STATUS_FILE}")
    print(f"Sections: {status['summary']['total_sections']}")
    print(f"Chapters: {status['summary']['total_chapters']}")
    print(f"Templates: {status['summary']['total_chapters']}")
    print(f"Legacy reserved prefixes: {LEGACY_RESERVED_PREFIXES}")


if __name__ == "__main__":
    main()
