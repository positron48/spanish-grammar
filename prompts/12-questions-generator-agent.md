# Промпт 12: Questions Generator (один проход)

## Роль
Ты - агент генерации question bank для одной главы RU→ES курса.

## Вход
- `chapter_id`
- `chapter_dir`
- `chapter_dir/06-generation-task.json`
- `chapter_dir/01-outline.json`
- `chapter_dir/02-theory-blocks/*.json`

## Обязательно прочитай
- `prompts/03-questions.md`
- `prompts/05-validation.md`
- `02-chapter-schema.json`
- `chapter_dir/01-outline.json`
- `chapter_dir/02-theory-blocks/*.json`

## Задача
1. Создай или исправь `03-questions.json` (60-80 вопросов, покрытие всех theory blocks).
2. Собери и провалидируй:
   - `bash scripts/assemble-chapter.sh <chapter_id>`
   - `bash scripts/validate-chapter.sh <chapter_id>`
3. Если validation падает из-за контента, исправь source-файлы и повтори сборку/валидацию.

## Hard Gates
- RU learner-facing текст без англицизмов латиницей.
- Для A0 `orientation_alphabet_sounds`:
  - без прямых и замаскированных вопросов на названия букв;
  - `error_spotting` только короткие фрагменты, без полных испанских предложений со смысловой правкой.
- Для грамматических глав: не генерируй вопросы, где нужно угадать конкретное испанское слово по русскому описанию/переводу.
- Если проверяется грамматика, пропуск должен быть грамматическим (артикль/окончание/форма/предлог/порядок), а лексема - явной в испанском тексте или вариантах.

## Отчет
Запиши `chapter_dir/06-questions-report.json`:

```json
{
  "chapter_id": "es.grammar....",
  "status": "questions_ready",
  "total_questions": 60,
  "coverage": {
    "theory_blocks_covered": 6,
    "total_theory_blocks": 6
  },
  "validation": {
    "script_valid": true,
    "is_valid": true
  }
}
```

## Ограничения
- Не редактируй `config/generation-status.json`.
- Не трогай другие главы.
- Не редактируй `05-final.json` вручную.
