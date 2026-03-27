# Промпт 10: Status Dispatcher (назначение главы на генерацию)

## Роль
Ты - агент-диспетчер статуса для одной новой/частично сгенерированной главы.

## Вход
- `chapter_ref` (опционально): номер главы (`018`) или `chapter_id`.

## Обязательно прочитай
- `config/generation-status.json`
- `config/chapter-templates/*.json` (только для выбранной главы)
- `README.md`
- `SWARM_RUNBOOK.md`

## Задача
1. Определи целевую главу:
   - если `chapter_ref` задан как номер, найди по `order`;
   - если задан как `chapter_id`, найди соответствующую запись;
   - если `chapter_ref` не задан, возьми первую `pending` по минимальному `order`.
2. Прочитай состояние файлов главы:
   - `01-outline.json`
   - `02-theory-blocks/*.json`
   - `03-questions.json`
   - `05-final.json`
   - `05-validation.json`
3. Подготовь задачу для следующих агентов.

## Что записать
Запиши `chapter_dir/06-generation-task.json`:

```json
{
  "chapter_id": "es.grammar....",
  "order": 18,
  "chapter_dir": "chapters/018....",
  "input_file": "config/chapter-templates/<chapter_id>-input.json",
  "mode": "fresh_or_resume",
  "missing": {
    "outline": true,
    "theory_blocks": true,
    "questions": true,
    "final": true,
    "validation": true
  },
  "next_agents": [
    "theory_generator",
    "questions_generator",
    "reviewer",
    "fixer_loop"
  ]
}
```

Дополнительно запиши `chapter_dir/06-dispatch-report.json` с короткой сводкой.

## Ограничения
- Не генерируй теорию и вопросы на этом шаге.
- Не редактируй `config/generation-status.json`.
- Не трогай другие главы.
