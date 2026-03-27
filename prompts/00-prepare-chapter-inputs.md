# Промпт: Подготовка machine-readable входных файлов из 01-sections.md

## Задача
Синхронизировать машинные артефакты курса Spanish grammar из `01-sections.md`.

## Источник истины
- `01-sections.md` - человекочитаемый outline курса

## Что нужно обновить
1. `config/generation-status.json`
2. `config/chapter-templates/*.json`

## Как выполнять
1. Не парси файл вручную и не создавай 152 шаблона руками.
2. Запусти:
   ```bash
   make sync-plan
   ```
   или:
   ```bash
   python3 scripts/sync-course-plan.py
   ```
3. Проверь, что:
   - количество секций и глав в `summary` совпадает с `01-sections.md`;
   - для каждой главы есть `config/chapter-templates/<chapter_id>-input.json`;
   - `target_language` в шаблонах равен `es`, `ui_language` равен `ru`.

## Важные правила
- `config/generation-status.json` и `config/chapter-templates/*.json` считаются производными от `01-sections.md`.
- Если структура курса изменилась, сначала правь `01-sections.md`, затем снова запускай sync.
- Не редактируй generated файлы вручную, если проблему можно исправить через `scripts/sync-course-plan.py`.
- Текущий legacy placeholder занимает префикс `001.*`, поэтому новые output directories начинаются с `002.*`.

## Формат ответа
После завершения выведи краткую сводку:
- сколько секций обнаружено;
- сколько глав создано в status файле;
- сколько chapter templates создано;
- какие файлы были обновлены.
