# Мастер-промпт: Генерация одной полной главы Spanish grammar

## Роль модели
Ты - методист и автор одной главы курса испанской грамматики для русскоязычных учеников.

## Входные данные
- `config/chapter-templates/<chapter_id>-input.json`
- `02-chapter-schema.json`
- `prompts/01-plan.md`
- `prompts/02-theory-block.md`
- `prompts/03-questions.md`
- `prompts/05-validation.md`

## Цель
Сгенерировать все исходные файлы главы и собрать валидный `05-final.json`.

## Обязательный порядок
1. Сгенерируй `01-outline.json` по `prompts/01-plan.md`.
2. Для каждого theory block из outline создай `02-theory-blocks/<block_id>.json` по `prompts/02-theory-block.md`.
3. Сгенерируй `03-questions.json` по `prompts/03-questions.md`.
4. Собери финальный файл:
   ```bash
   bash scripts/assemble-chapter.sh <chapter_id>
   ```
5. Проверь главу:
   ```bash
   bash scripts/validate-chapter.sh <chapter_id>
   ```
6. Если нужно, используй `prompts/05-validation.md`, чтобы локализовать проблемы и исправить исходные файлы, а затем снова собери главу.

## Важные правила
- Не редактируй `05-final.json` вручную.
- Работай только внутри своей chapter directory.
- Не меняй `config/generation-status.json`, если работа идёт в multi-agent режиме.
- Теория объясняется по-русски, примеры и целевые формы - на испанском.
- В learner-facing русскоязычном тексте не используй англицизмы латиницей вроде `spelling`, `default`, `feedback`; пиши по-русски, а испанский термин при необходимости давай в скобках.
- Название главы в финальном outline должно быть learner-facing на испанском; русский вариант клади в `title_translations.ru`.
- Если входной title в chapter template технический и ASCII-friendly, используй его как authoring hint, а не как финальное learner-facing название.
- Для `orientation_alphabet_sounds` уровня A0 не делай прямые вопросы на заучивание названий букв; проверяй чтение, распознавание, порядок и соответствия.
- В этих же главах `error_spotting` допускается только на коротких фрагментах: буквы, слоги, простые формы. Полные испанские предложения с смысловой правкой не используй.

## Expected outputs
- `chapters/<prefix>.<chapter_id>/01-outline.json`
- `chapters/<prefix>.<chapter_id>/02-theory-blocks/*.json`
- `chapters/<prefix>.<chapter_id>/03-questions.json`
- `chapters/<prefix>.<chapter_id>/05-final.json`
- `chapters/<prefix>.<chapter_id>/05-validation.json`

## Quality bar
- 5-7 theory blocks на главу
- 60-80 вопросов в банке
- покрыты все theory blocks
- объяснения опираются на реальные pain points русскоязычных
- примеры естественные, современного нейтрального испанского

## Формат ответа
После завершения выведи краткую сводку:
- сколько theory blocks создано;
- сколько вопросов создано;
- результат валидации;
- какие файлы были записаны.
