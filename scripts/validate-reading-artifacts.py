#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def validate(course_root: pathlib.Path, covers_optional: bool) -> int:
    errors = []
    for final_path in course_root.glob("chapters/*/05-final.json"):
        data = json.loads(final_path.read_text(encoding="utf-8"))
        for block in data.get("blocks", []):
            if block.get("type") != "reading_passage":
                continue
            rp = block.get("reading_passage", {})
            for seg in rp.get("segments", []):
                audio_rel = seg.get("audio_rel_path", "")
                if not audio_rel:
                    errors.append(f"{final_path}: missing audio_rel_path")
                    continue
                audio_abs = course_root / audio_rel
                if not audio_abs.exists():
                    errors.append(f"{final_path}: missing audio file {audio_rel}")

    scripts_dir = pathlib.Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import reading_catalog_maintain as rcm

    for line in rcm.scan_reading_catalog_issues(course_root, "reading", 40):
        errors.append(line)
    for line in rcm.scan_reading_cover_issues(course_root, "reading", covers_optional=covers_optional):
        errors.append(line)

    if errors:
        for err in errors:
            print(err)
        return 1
    print("reading artifacts validated")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--covers-optional", action="store_true", help="warn-only for missing covers")
    args = parser.parse_args()
    root = pathlib.Path(".").resolve()
    sys.exit(validate(root, args.covers_optional))
