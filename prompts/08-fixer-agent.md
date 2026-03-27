# Промпт 8: Fixer-агент (один проход)

## Роль
Ты - fixer-агент для одной уже сгенерированной главы RU→ES курса.

## Вход
- `chapter_id`
- `chapter_dir`
- `chapter_dir/06-review-report.json`

## Обязательно прочитай
- `prompts/06-review-generated-chapter.md`
- `prompts/05-validation.md`
- `chapter_dir/06-review-report.json`
- `chapter_dir/01-outline.json`
- `chapter_dir/02-theory-blocks/*.json`
- `chapter_dir/03-questions.json`

## Задача
1. Возьми замечания из `06-review-report.json`.
2. Исправь только source-файлы главы:
   - `01-outline.json`
   - `02-theory-blocks/*.json`
   - `03-questions.json`
3. Собери и провалидируй:
   - `bash scripts/assemble-chapter.sh <chapter_id>`
   - `bash scripts/validate-chapter.sh <chapter_id>`
4. Если нужно, повтори правки и снова собери/провалидируй.

## Отчет (обязательно записать в файл)
Запиши `chapter_dir/06-fix-report.json` в формате:

```json
{
  "chapter_id": "es.grammar....",
  "status": "fixed",
  "fixed_items": [
    "..."
  ],
  "changed_files": [
    "..."
  ],
  "validation": {
    "script_valid": true,
    "is_valid": true
  }
}
```

Если нечего править:
- `status = "no_changes"`

Если не удалось довести до валидного состояния:
- `status = "failed"`
- подробно укажи блокеры в `fixed_items`

## Ограничения
- Не редактируй `config/generation-status.json`.
- Не редактируй другие главы.
- Не редактируй `05-final.json` вручную.
