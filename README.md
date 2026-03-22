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
| `config/generation-status.json` | Секции и список `chapter_ids` (как у английского курса). |
| `config/chapter-templates/` | Шаблоны для новых глав (по мере наполнения). |
| `chapters/<prefix>.es.grammar.../<stage>.json` | Исходники главы; итог — `05-final.json`. |
| `scripts/` | `assemble-chapter.sh`, `validate-chapter.sh`, утилиты (как в english-grammar). |
| `02-chapter-schema.json` | JSON Schema для контента главы. |

## Команды (см. Makefile)

- `make final` / `make validate-all` — по аналогии с english-grammar.
- Полная сборка bundle в Go-проект — только через `scripts/generate-grammar-bundle.sh` в корне монорепо.

## Именование

Префикс id глав и секций: `es.grammar.<section>.<chapter_slug>` — в одном стиле с `en.grammar.*`.
