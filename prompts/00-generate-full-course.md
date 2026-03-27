# Мастер-промпт: Координация генерации всего курса Spanish grammar

## Роль модели
Ты - координатор генерации курса испанской грамматики для русскоязычных учеников.

## Цель
Сгенерировать курс по батчам, не ломая общий status файл и не редактируя вручную `05-final.json`.

## Входные данные
- `01-sections.md`
- `config/generation-status.json`
- `config/chapter-templates/*.json`
- `02-chapter-schema.json`
- `prompts/00-generate-full-chapter.md`
- `prompts/01-plan.md`
- `prompts/02-theory-block.md`
- `prompts/03-questions.md`
- `prompts/05-validation.md`
- `SWARM_RUNBOOK.md`

## Подготовка
1. Если `generation-status.json` или chapter templates не соответствуют `01-sections.md`, сначала выполни:
   ```bash
   make sync-plan
   ```
2. Прочитай `SWARM_RUNBOOK.md` и определи батч.
3. Работай по `order` из `config/generation-status.json`.

## Правило параллельной работы
- В multi-agent режиме `config/generation-status.json` обновляет только координатор.
- Worker-агенты не должны менять shared status файл параллельно.
- Worker владеет только своей директорией `chapters/<prefix>.<chapter_id>/`.
- Координатор после завершения worker-задачи переводит статус главы в `generated` или `validated`.

## Рекомендуемый процесс
1. Выбери батч (например, одна секция или 4-6 глав подряд).
2. Для каждой главы со статусом `pending`:
   - переведи её в `in_progress` только если работа идёт в одном агенте;
   - либо назначь chapter worker по `prompts/00-generate-full-chapter.md`;
   - после завершения проверь наличие:
     - `01-outline.json`
     - `02-theory-blocks/*.json`
     - `03-questions.json`
     - `05-final.json`
     - `05-validation.json`
3. Прогони:
   ```bash
   bash scripts/validate-chapter.sh <chapter_id>
   ```
4. Обнови `config/generation-status.json`:
   - `generated`, если файлы созданы;
   - `validated`, если `05-validation.json` сообщает `is_valid: true`.
5. После батча при необходимости обнови bundle:
   ```bash
   ./scripts/generate-grammar-bundle.sh es
   ```

## Важные правила
- Не создавай `05-final.json` руками: только через `scripts/assemble-chapter.sh` или `make final`.
- Не запускай сразу два worker-а на одну и ту же главу.
- Не меняй чужие chapter directories.
- Если chapter template уже существует, используй его как source of truth для входных параметров.
- Learner-facing chapter title в `01-outline.json` должен быть на испанском, с русским переводом в `title_translations.ru`.

## Definition of Done для батча
- Все главы батча имеют статус не ниже `generated`.
- У валидных глав есть `05-validation.json`.
- `summary` в `config/generation-status.json` обновлён.
- При необходимости обновлён embedded bundle `es`.

## Формат ответа
После каждого батча выведи:
- какие главы обработаны;
- какие статусы выставлены;
- что осталось в `pending`;
- какие главы требуют ручного разбора.
