# Spanish grammar course (authoring)

Репозиторий курса по **той же схеме**, что и [`../english-grammar`](../english-grammar): главы в `chapters/`, сборка `final.json`, валидация, опционально admin/test dev-серверы из Makefile.

## Связь с приложением

- Источник истины для **встроенного** bundle в бинарнике: после правок запускайте из **корня** `english-ai-bot`:

  ```bash
  ./scripts/generate-grammar-bundle.sh es
  # или оба языка:
  ./scripts/generate-grammar-bundle.sh all
  ```

- Скрипт копирует `config/generation-status.json` → `internal/grammarbundle/es/sections.json`, главы из `chapters/*/05-final.json` (или `04-final.json`) → `internal/grammarbundle/es/chapters/<chapter_id>.json`, генерирует `index.json`.

- Runtime: `GRAMMAR_BUNDLE_ID=es` (или `GRAMMAR_BUNDLE_DIR` на эту папку в dev).

## Структура

| Путь | Назначение |
|------|------------|
| `01-sections.md` | Человекочитаемый outline курса от A0 до C1; главный source of truth для структуры. |
| `config/generation-status.json` | Секции и список `chapter_ids` (как у английского курса). |
| `config/chapter-templates/` | Шаблоны для новых глав (по мере наполнения). |
| `chapters/<prefix>.es.grammar.../<stage>.json` | Исходники главы; итог — `05-final.json`. |
| `prompts/` | Prompt templates для одиночной и пакетной генерации глав. |
| `prompts/06-review-generated-chapter.md` | Чеклист и workflow для reviewer-агента по уже сгенерированным главам. |
| `prompts/07-reviewer-agent.md` | Роль reviewer-агента (один проход, только замечания). |
| `prompts/08-fixer-agent.md` | Роль fixer-агента (исправления по report + пересборка/валидация). |
| `prompts/09-review-fix-loop.md` | Оркестратор цикла reviewer→fixer→reviewer для одной главы. |
| `prompts/10-status-dispatcher-agent.md` | Диспетчер статуса для запуска генерации одной главы. |
| `prompts/11-theory-generator-agent.md` | Агент генерации теории (outline + theory blocks). |
| `prompts/12-questions-generator-agent.md` | Агент генерации вопросов (question bank + assemble/validate). |
| `prompts/13-generation-reviewer-agent.md` | Reviewer-проход для новой главы после генерации. |
| `prompts/14-generation-fixer-agent.md` | Fixer-проход по findings reviewer-а для новой главы. |
| `prompts/15-generate-chapter-swarm-loop.md` | Оркестратор полного pipeline генерации одной главы. |
| `SWARM_RUNBOOK.md` | Процесс пакетной генерации роями агентов без конфликтов по shared state. |
| `STRICT_SEQUENTIAL_SWARM_PROMPT.md` | Готовый prompt для нового контекста: строгая последовательная генерация глав с hard validation gate. |
| `scripts/` | `assemble-chapter.sh`, `validate-chapter.sh`, `sync-course-plan.py` и утилиты (как в english-grammar). |
| `02-chapter-schema.json` | JSON Schema для контента главы. |

## Жесткие правила генерации

- В learner-facing русскоязычных текстах не использовать англицизмы латиницей вроде `spelling`, `default`, `feedback`; вместо них писать по-русски, а испанский термин при необходимости давать в скобках.
- Для стартовых глав `orientation_alphabet_sounds` уровня A0 не задавать прямые вопросы на заучивание названий букв; проверять чтение, распознавание, порядок и соответствия.
- В этих же главах `error_spotting` допускается только на коротких фрагментах: буквы, слоги, простые формы. Полные испанские предложения с смысловой правкой не использовать.

## Команды (см. Makefile)

- `make sync-plan` — пересобрать `config/generation-status.json` и `config/chapter-templates/*.json` из `01-sections.md`.
- `make final` / `make validate-all` — по аналогии с english-grammar.
- Полная сборка bundle в Go-проект — только через `scripts/generate-grammar-bundle.sh` в корне монорепо.

## Workflow

1. Правим `01-sections.md`.
2. Запускаем `make sync-plan`.
3. Генерируем главы по `prompts/*.md` и `SWARM_RUNBOOK.md`.
4. Собираем `05-final.json` только через `scripts/assemble-chapter.sh` / `make final`.
5. После батча при необходимости обновляем embedded bundle: `./scripts/generate-grammar-bundle.sh es`.

## Review/Fix Loop в Codex UI

Для уже сгенерированной главы запускай цикл без bash-лупов, средствами роя агентов:
- `Use $spanish-review-fix-swarm for chapter 017`

Где `017` можно заменить на нужный `order` или `chapter_id`.

Для генерации новой/частично готовой главы:
- `Use $spanish-generate-chapter-swarm to generate chapter 018`

Где `018` можно заменить на нужный `order` или `chapter_id`.

## Именование

Префикс id глав и секций: `es.grammar.<section>.<chapter_slug>` — в одном стиле с `en.grammar.*`.
