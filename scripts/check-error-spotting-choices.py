#!/usr/bin/env python3
"""
Проверка error_spotting: находит вопросы с менее чем 4 вариантами ответа (нужно 1 правильный + минимум 3 неправильных).
Также помечает вопросы, где в промпте дублируется предложение при формулировке «выберите правильный вариант».
Вывод: список глав и question id для ручной правки.
"""

import json
import re
from pathlib import Path


def has_sentence_in_prompt(prompt: str) -> bool:
    """Есть ли в промпте явно вынесенное предложение (в ** или кавычках)."""
    if not prompt:
        return False
    # **...** или "..." или «...»
    if re.search(r'\*\*[^*]+\*\*', prompt):
        return True
    if re.search(r'["\'][^"\']+["\']', prompt):
        return True
    if '«' in prompt and '»' in prompt:
        return True
    return False


def choices_are_full_sentences(choices: list) -> bool:
    """Варианты выглядят как целые предложения (а не «X → Y»)."""
    if not choices:
        return False
    for c in choices[:3]:  # проверяем до 3
        t = (c.get('text') or '').strip()
        if not t:
            continue
        # «X → Y» — не предложение
        if ' → ' in t or ('→' in t and len(t) < 50):
            return False
        # Обычно предложение: первая буква заглавная, есть . или ? в конце или по пути
        if t[0].isupper() and (t.endswith('.') or t.endswith('?') or t.endswith('!') or len(t) > 15):
            return True
    return True  # по умолчанию считаем предложениями


def main():
    project = Path(__file__).resolve().parent.parent
    chapters_dir = project / 'chapters'

    need_fix = []  # (chapter_name, qid, n_choices, prompt_preview, has_sentence_in_prompt)

    for ch in sorted(chapters_dir.iterdir()):
        if not ch.is_dir() or ch.name.startswith('.'):
            continue
        f = ch / '05-final.json'
        if not f.exists():
            continue
        try:
            data = json.load(open(f, encoding='utf-8'))
            for q in data.get('question_bank', {}).get('questions', []):
                if q.get('type') != 'error_spotting':
                    continue
                choices = q.get('choices', [])
                n = len(choices)
                if n >= 4:
                    continue
                prompt = (q.get('prompt') or '').strip()
                prompt_preview = (prompt[:70] + '…') if len(prompt) > 70 else prompt
                has_sent = has_sentence_in_prompt(prompt)
                full_sent = choices_are_full_sentences(choices)
                should_remove_sentence = (
                    full_sent and has_sent and
                    ('Выберите правильный' in prompt or 'Найдите ошибку' in prompt)
                )
                need_fix.append((ch.name, q.get('id'), n, prompt_preview, has_sent, should_remove_sentence))
        except Exception as e:
            print(f"# Ошибка в {ch.name}: {e}", file=__import__('sys').stderr)

    if not need_fix:
        print("✓ Все error_spotting имеют ≥4 вариантов.")
        return

    print(f"# error_spotting с <4 вариантами: {len(need_fix)}")
    print("# Требуется: 1 правильный + минимум 3 неправильных. В промпте не дублировать предложение при «выберите правильный вариант».")
    print()

    for ch_name, qid, n, preview, has_sent, should_rm in need_fix:
        flags = []
        if should_rm:
            flags.append("убрать предложение из промпта")
        if has_sent and not should_rm:
            flags.append("предложение в промпте")
        fl = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{ch_name}  {qid}  choices={n}  {preview}{fl}")


if __name__ == '__main__':
    main()
