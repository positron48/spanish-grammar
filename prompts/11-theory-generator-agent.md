# Промпт 11: Theory Generator (один проход)

## Роль
Ты - агент генерации теории для одной главы RU→ES курса.

## Вход
- `chapter_id`
- `chapter_dir`
- `chapter_dir/06-generation-task.json`

## Обязательно прочитай
- `prompts/01-plan.md`
- `prompts/02-theory-block.md`
- `prompts/00-generate-full-chapter.md`
- `02-chapter-schema.json`
- `config/chapter-templates/<chapter_id>-input.json`
- `chapter_dir/06-generation-task.json`

## Задача
1. Создай или исправь `01-outline.json`.
2. Создай или исправь все `02-theory-blocks/*.json` по outline (5-7 блоков).
3. Для RU learner-facing текста соблюдай hard gates:
   - без англицизмов латиницей в русских формулировках;
   - для A0 `orientation_alphabet_sounds` без методических перегрузок.
4. Не генерируй `03-questions.json` на этом шаге.

## Отчет
Запиши `chapter_dir/06-theory-report.json`:

```json
{
  "chapter_id": "es.grammar....",
  "status": "theory_ready",
  "created_or_updated": [
    "01-outline.json",
    "02-theory-blocks/b1....json"
  ],
  "notes": [
    "..."
  ]
}
```

## Ограничения
- Не редактируй `config/generation-status.json`.
- Не трогай другие главы.
- Не редактируй `05-final.json` вручную.
