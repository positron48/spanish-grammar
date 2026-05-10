#!/usr/bin/env python3
"""
Rename verb_forms lemma JSON files and artifacts so headword = Spanish infinitive (Jehle CSV).

Usage (from repo root or spanish-grammar):
  python3 scripts/normalize-verb-forms-lemmas.py --course-root . --dry-run
  python3 scripts/normalize-verb-forms-lemmas.py --course-root . --apply

Duplicate targets (e.g. carga.json + cargo.json -> cargar.json): keeps lexicographically first source stem,
removes the other file(s). Rebuilds training_pack/verb_forms/index.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def repo_root_from_course(course_root: Path) -> Path:
    cr = course_root.resolve()
    # spanish-grammar -> english-ai-bot
    if (cr / "training_pack").is_dir():
        return cr.parent.parent
    return cr


# -ar nouns / non-infinitives that would otherwise match the infinitive heuristic
_INFINITIVE_BLOCKLIST = frozenset(
    {
        "ayer",
        "lugar",
        "mujer",
        "líder",
        "lider",
        "azar",  # noun; not a verb infinitive in standard Spanish
    }
)


def looks_like_spanish_infinitive_lemma(s: str) -> bool:
    """Rough filter: Spanish dictionary infinitive shape (-ar/-er/-ir or reflexive)."""
    key = s.strip().lower()
    if key in _INFINITIVE_BLOCKLIST:
        return False
    if key in ("ir", "dar", "ser", "ver", "reír", "reir"):
        return True
    if len(key) < 2:
        return False
    if key.endswith(("arse", "erse", "irse")) and len(key) >= 5:
        return True
    if key.endswith("ar") and len(key) >= 4:
        return True
    if key.endswith("er") and len(key) >= 4:
        return True
    if key.endswith("ir") and len(key) >= 3:
        return True
    return False


def load_jehle_maps(csv_paths: List[Path]) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Returns (infinitives, form_lowercase -> set of infinitive lemmas)."""
    infinitives: Set[str] = set()
    form_to_lemmas: Dict[str, Set[str]] = defaultdict(set)
    form_cols = ("form_1s", "form_2s", "form_3s", "form_1p", "form_2p", "form_3p", "gerund", "pastparticiple")

    for csv_path in csv_paths:
        if not csv_path.exists():
            continue
        with csv_path.open(encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                lem = (row.get("infinitive") or "").strip().lower()
                if not lem:
                    continue
                infinitives.add(lem)
                for col in form_cols:
                    cell = (row.get(col) or "").strip().lower()
                    if cell:
                        form_to_lemmas[cell].add(lem)

    return infinitives, form_to_lemmas


def resolve_target_lemma(
    stem: str,
    infinitives: Set[str],
    form_to_lemmas: Dict[str, Set[str]],
    overrides: Dict[str, str],
) -> Tuple[Optional[str], str]:
    """
    Returns (target_lemma, reason) or (None, error_note).
    """
    key = stem.strip().lower()
    if key in overrides:
        return overrides[key], "override"
    if key in infinitives:
        return key, "already_infinitive"
    cands = form_to_lemmas.get(key)
    if cands:
        if len(cands) == 1:
            return next(iter(cands)), "unique_form_match"
        pick = sorted(cands)[0]
        return pick, f"ambiguous_form_used_first_lexicographic:{','.join(sorted(cands))}"
    if looks_like_spanish_infinitive_lemma(key):
        return key, "heuristic_infinitive_shape"
    return None, "no_jehle_match"


def patch_card_strings(obj: dict, old_lemma: str, new_lemma: str) -> None:
    """Replace parenthetical (old) hints and stray old lemma tokens in string fields."""
    old_l = old_lemma.strip()
    new_l = new_lemma.strip()
    if old_l == new_l:
        return
    for field in ("question_es_with_blank", "translation_ru_full"):
        s = obj.get(field)
        if not isinstance(s, str) or not s:
            continue
        # Hint like "... (carga)" at end
        s2 = re.sub(
            rf"\(\s*{re.escape(old_l)}\s*\)",
            f"({new_l})",
            s,
            flags=re.IGNORECASE,
        )
        obj[field] = s2


def rebuild_index(pack_root: Path, generator_name: str) -> None:
    idx_path = pack_root / "index.json"
    prev = {}
    if idx_path.exists():
        prev = json.loads(idx_path.read_text(encoding="utf-8"))
    lemmas_dir = pack_root / "lemmas"
    lemmas_out: Dict[str, str] = {}
    for p in sorted(lemmas_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        lem = (data.get("lemma") or p.stem).strip()
        if not lem:
            continue
        lemmas_out[lem] = f"lemmas/{p.name}"
    out = {
        "version": prev.get("version", "v1"),
        "language": "es",
        "generated_at": prev.get("generated_at", ""),
        "generator": prev.get("generator", {"name": generator_name, "model": ""}),
        "generation_coverage": prev.get(
            "generation_coverage",
            {},
        ),
        "lemmas": lemmas_out,
    }
    idx_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course-root", default=".", help="Spanish grammar course root")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.apply == args.dry_run:
        print("Specify exactly one of --dry-run or --apply", file=sys.stderr)
        return 2

    course_root = Path(args.course_root).resolve()
    pack_root = course_root / "training_pack" / "verb_forms"
    lemmas_dir = pack_root / "lemmas"
    if not lemmas_dir.is_dir():
        print(f"Missing {lemmas_dir}", file=sys.stderr)
        return 1

    repo_root = repo_root_from_course(course_root)
    csv_paths = [
        repo_root / "resources" / "verbs" / "jehle_verb_database.csv",
        repo_root / "resources" / "verbs" / "jehle_supplement_aux_haber.csv",
    ]
    infinitives, form_to_lemmas = load_jehle_maps(csv_paths)

    # Non-infinitive headwords / Jehle gaps (participles, conjugated forms, nouns used as filenames).
    overrides: Dict[str, str] = {
        "canto": "cantar",
        "embargo": "embargar",
        "bloqueo": "bloquear",
        "resto": "restar",
        "juzgado": "juzgar",
        "mediado": "mediar",
        # Prefer simple verb over reflexive when Jehle lists both (script picks lexicographically).
        "comunicado": "comunicar",
        "llamado": "llamar",
    }

    stems = sorted({p.stem for p in lemmas_dir.glob("*.json")})
    resolutions: Dict[str, Tuple[Optional[str], str]] = {}
    for stem in stems:
        resolutions[stem] = resolve_target_lemma(stem, infinitives, form_to_lemmas, overrides)

    # Group sources by target lemma (successful resolutions only)
    by_target: Dict[str, List[str]] = defaultdict(list)
    problems: List[str] = []
    for stem, (tgt, reason) in resolutions.items():
        if tgt is None:
            problems.append(f"  {stem}.json -> FAILED ({reason})")
            continue
        by_target[tgt].append(stem)
        print(f"  {stem}.json -> {tgt}.json ({reason})")

    unresolved_stems = {st for st, (tg, _) in resolutions.items() if tg is None}

    if problems:
        print("\nUnresolved (need manual overrides or csv):", file=sys.stderr)
        for line in problems:
            print(line, file=sys.stderr)

    # For each target, pick canonical source stem (first lexicographically)
    canonical_source: Dict[str, str] = {}
    for tgt, sources in sorted(by_target.items()):
        canon = sorted(sources)[0]
        canonical_source[tgt] = canon
        extra = [s for s in sources if s != canon]
        if extra:
            print(f"\n[target={tgt}] keep {canon}.json, drop duplicates: {', '.join(s + '.json' for s in extra)}")

    if args.dry_run:
        print("\nDry run — no files changed.")
        return 0 if not problems else 1

    # Apply: for each target infinitive, take canonical source file, patch, write {tgt}.json
    for tgt, canon_stem in sorted(canonical_source.items()):
        src_path = lemmas_dir / f"{canon_stem}.json"
        dst_path = lemmas_dir / f"{tgt}.json"
        if not src_path.exists():
            print(f"skip missing {src_path.name}", file=sys.stderr)
            continue
        data = json.loads(src_path.read_text(encoding="utf-8"))
        old_in_json = (data.get("lemma") or canon_stem).strip()
        data["lemma"] = tgt
        for card in data.get("cards") or []:
            if isinstance(card, dict):
                patch_card_strings(card, old_in_json, tgt)
                patch_card_strings(card, canon_stem, tgt)
        out_bytes = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        dst_path.write_text(out_bytes, encoding="utf-8")
        if src_path.resolve() != dst_path.resolve() and src_path.exists():
            src_path.unlink()
            print(f"renamed {canon_stem}.json -> {tgt}.json")

    # Remove duplicate / obsolete json (resolved stems that are not the final filename)
    expected = {f"{t}.json" for t in canonical_source}
    for p in list(lemmas_dir.glob("*.json")):
        if p.stem in unresolved_stems:
            continue
        if p.name not in expected:
            p.unlink()
            print(f"delete {p.name}")

    rebuild_index(pack_root, "normalize-verb-forms-lemmas.py")
    print(f"\nDone. Index rebuilt at {pack_root / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
