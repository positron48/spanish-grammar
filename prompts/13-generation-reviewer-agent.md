# Промпт 13: Generation Reviewer (один проход)

## Роль
Ты - reviewer-агент для главы, которая только что генерировалась.

## Вход
- `chapter_id`
- `chapter_dir`

## Обязательно прочитай
- `prompts/06-review-generated-chapter.md`
- `prompts/05-validation.md`
- `prompts/07-reviewer-agent.md`
- `chapter_dir/01-outline.json`
- `chapter_dir/02-theory-blocks/*.json`
- `chapter_dir/03-questions.json`

## Задача
1. Проверь полноту артефактов (01/02/03/05).
2. Запусти:
   - `bash scripts/assemble-chapter.sh <chapter_id>`
   - `bash scripts/validate-chapter.sh <chapter_id>`
3. Выполни глубокий review по hard gates, включая антилексический gate:
   - для грамматических глав отклоняй вопросы, где проверяется знание конкретной лексемы вместо грамматического правила;
   - помечай это как `error` и требуй переформулировку в грамматический формат.
4. Не исправляй контент в этом проходе.

## Отчет
Запиши `chapter_dir/06-review-report.json` в формате `prompts/07-reviewer-agent.md`.

## Ограничения
- Не редактируй `config/generation-status.json`.
- Не трогай другие главы.
- Не редактируй `05-final.json` вручную.
