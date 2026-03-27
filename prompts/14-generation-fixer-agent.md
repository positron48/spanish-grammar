# Промпт 14: Generation Fixer (один проход)

## Роль
Ты - fixer-агент для только что сгенерированной главы.

## Вход
- `chapter_id`
- `chapter_dir`
- `chapter_dir/06-review-report.json`

## Обязательно прочитай
- `prompts/06-review-generated-chapter.md`
- `prompts/08-fixer-agent.md`
- `chapter_dir/06-review-report.json`
- `chapter_dir/01-outline.json`
- `chapter_dir/02-theory-blocks/*.json`
- `chapter_dir/03-questions.json`

## Задача
1. Исправь все findings из `06-review-report.json`.
2. Редактируй только source:
   - `01-outline.json`
   - `02-theory-blocks/*.json`
   - `03-questions.json`
3. Запусти:
   - `bash scripts/assemble-chapter.sh <chapter_id>`
   - `bash scripts/validate-chapter.sh <chapter_id>`
4. Если после правок остаются ошибки, повтори до чистого скриптового validation.

## Отчет
Запиши `chapter_dir/06-fix-report.json` в формате `prompts/08-fixer-agent.md`.

## Ограничения
- Не редактируй `config/generation-status.json`.
- Не трогай другие главы.
- Не редактируй `05-final.json` вручную.
