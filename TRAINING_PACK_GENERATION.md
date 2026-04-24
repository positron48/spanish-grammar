# Spanish Grammar: генерация training pack

Этот документ описывает полный процесс генерации `training_pack` в `courses/spanish-grammar`:  
что где лежит, какие промпты используются, как запускать генерацию/валидацию и где задавать параметры локальной LLM.

---

## 1) Что это и зачем

`training_pack` — это отдельный артефакт с вопросами для режима **Grammar SRS** в приложении.

Ключевые принципы:
- курс (`chapters/*/05-final.json`) остаётся source of truth по теории;
- `training_pack` генерируется **внутри курса**;
- приложение только читает готовые JSON, не вызывает LLM в runtime;
- если pack пустой/невалидный, режим тренировки в приложении должен быть недоступен.

---

## 2) Структура файлов

### Источники (вход)

- `chapters/*/05-final.json` (или `04-final.json` fallback)
- `prompts/16-training-pack-generator-system.md` — системный промпт генератора
- `config/training-pack.json` — дефолтные параметры генератора
- `scripts/fill-training-pack.py` — оркестратор массовой догенерации до порога валидных вопросов

### Артефакты (выход)

- `training_pack/index.json`
- `training_pack/chapters/es.XXX.000.<chapter_id>.questions.json` (префикс с номером главы)
- `training_pack/reports/build-report.json`
- `training_pack/reports/validation-report.json`
- `training_pack/runs/<timestamp>/es.XXX.YYY.<chapter_id>.<block_id>.raw.json` (сырой ответ LLM)

---

## 3) Контракт формата

### `training_pack/index.json`

Минимальные поля:
- `version`
- `language` (`es`)
- `course_id` (`spanish-grammar`)
- `generated_at`
- `generator_version`
- `mode` (`llm-only`)
- `prompt_version`
- `chapters` (`chapter_id -> file_name`)

### `training_pack/chapters/*.questions.json`

Поля:
- `chapter_id`
- `course_version`
- `questions[]`
- `meta`

Каждый вопрос после генератора обязан иметь:
- `id`
- `type` (`mcq_single`)
- `prompt`
- `correct_answer`
- `explanation`
- `theory_block_id`
- `chapter_id`
- `concept_id` (может быть пустым, если source не содержит)
- `difficulty` (нормализуется в диапазон `1..5`)
- `signature` (для антидубликата)

---

## 4) Промпты и их роль

Основной файл:
- `prompts/16-training-pack-generator-system.md`

Он задаёт:
- допустимые типы вопросов;
- обязательные поля JSON;
- ограничения качества (без бессмысленных distractors);
- запрет на проверку знаний за пределами целевого `theory_block_id`;
- запрет на дословное копирование примеров из теории.

Если хотите менять стиль/строгость генерации — править в первую очередь этот файл.

---

## 5) Режим генерации (только LLM)

Генераторы:
- `scripts/generate-training-pack.py` — точечная генерация (один/несколько блоков)
- `scripts/fill-training-pack.py` — последовательная генерация по всем блокам до целевого порога

Генератор работает **только через локальную LLM** и генерирует вопросы **с нуля**.

Дополнительно есть 2 режима записи:
- replace (по умолчанию): для целевого блока заменяет ранее сгенерированные вопросы;
- append (`--append`): добавляет новые вопросы к уже существующим.

Команды:

```bash
# базовая генерация (replace mode)
make training-pack

# догенерация новых вопросов (append mode)
make training-pack-append

# массовая догенерация по всем блокам до целевого порога
make training-pack-fill
```

`training-pack-fill` использует `--append` под капотом и по каждому theory-блоку повторяет генерацию батчами, пока валидных вопросов не станет >= target.

---

## 6) Где задавать параметры и креды локальной LLM

## Важно

Для **Ollama** обычно отдельные креды не нужны (локальный daemon).

### Базовые параметры

Можно задать через `config/training-pack.json`:
- `defaults.min_per_block`
- `defaults.questions_per_block`
- `defaults.llm_model`
- `defaults.ollama_url`

Можно переопределить env-переменными:
- `OLLAMA_URL`
- `TRAINING_PACK_MODEL`

Пример:

```bash
export OLLAMA_URL="http://127.0.0.1:11434"
export TRAINING_PACK_MODEL="qwen2.5:14b-instruct"
make training-pack
```

### Если используете не Ollama, а OpenAI-compatible локальный gateway

Скрипт сейчас ориентирован на Ollama API.  
Если у вас прокси с API-ключом, обычно добавляют:
- `LOCAL_LLM_BASE_URL`
- `LOCAL_LLM_API_KEY`

Рекомендуемый подход:
- хранить ключи только в локальном `.env.local` (вне git);
- не писать ключи в `README`, `Makefile`, JSON-конфиги репозитория;
- экспортировать в shell перед запуском.

Пример локального файла (не коммитить):

```bash
# .env.local (local only)
export OLLAMA_URL="http://127.0.0.1:11434"
export TRAINING_PACK_MODEL="qwen2.5:14b-instruct"
```

Запуск:

```bash
source .env.local
make training-pack
```

### Keep-alive модели

В запросах к Ollama используется:
- `keep_alive: "30m"`

То есть после вызова модель держится в памяти и выгружается примерно через 30 минут бездействия.

---

## 7) Полный workflow (рекомендуемый)

1. Обновить/собрать главы:

```bash
make final
```

2. Запустить генерацию pack малыми батчами:

```bash
# первый прогон (малое количество)
python3 scripts/generate-training-pack.py \
  --course-root . \
  --chapter-number 1 \
  --block-number 1 \
  --questions-per-block 3

# догенерация к тому же блоку
python3 scripts/generate-training-pack.py \
  --course-root . \
  --chapter-number 1 \
  --block-number 1 \
  --questions-per-block 3 \
  --append

# общие make-таргеты
make training-pack

make training-pack-append
```

3. Проверить отчёты:
- `training_pack/reports/validation-report.json`
- `training_pack/reports/build-report.json`

4. Проверить raw-ответы LLM (если llm-режим):
- `training_pack/runs/<timestamp>/*.raw.json`

5. Если отчёт/вопросы не ок:
- правите `prompts/16-training-pack-generator-system.md` и/или логику скрипта;
- перезапускаете тот же малый таргет (chapter/block).

6. После удачной точечной проверки:
- расширяете охват: больше `questions_per_block`, затем больше блоков/глав;
- в конце запускаете полную генерацию:

```bash
python3 scripts/fill-training-pack.py \
  --course-root . \
  --batch-size 3 \
  --target-valid 20
```

### Точечный массовый режим (для одной главы/блока)

```bash
# только глава 1
python3 scripts/fill-training-pack.py --course-root . --chapter-number 1 --batch-size 3 --target-valid 15

# только блок 1 в главе 1
python3 scripts/fill-training-pack.py --course-root . --chapter-number 1 --block-number 1 --batch-size 3 --target-valid 15
```

---

## 8) Что проверяет валидатор

Встроенные проверки:
- обязательные поля вопроса;
- корректность `type` (**только `mcq_single`**);
- непустой `prompt`;
- `prompt` содержит кириллицу (RU-интерфейс);
- наличие `correct_answer`;
- наличие `choices` и корректную ссылку `correct_answer -> choices[].id`;
- `explanation` содержит кириллицу;
- `choices[].text` содержит кириллицу;
- существование `theory_block_id` в theory-блоках главы;
- совпадение `chapter_id` вопроса и файла главы;
- дедуп внутри главы и между главами по `signature`;
- минимальная плотность вопросов на блок (`min_per_block`).

Если есть ошибки валидации — генератор завершается с кодом `2`.

Важно: текущая валидация **недеструктивная** — она формирует отчёт и статус, но не переписывает chapter-файл, чтобы `--append` не терял старые вопросы.

---

## 9) Интеграция с приложением

После успешной генерации в `courses/spanish-grammar`:

из корня `english-ai-bot`:

```bash
make grammar-training-pack
```

Это копирует pack в embedded-слой приложения (`internal/grammartrainingpack/es/...`).

---

## 10) Диагностика проблем

- `training_pack` пустой:
  - проверьте фильтры `--chapter-number`, `--block-number`;
  - проверьте доступность модели (`OLLAMA_URL`, `TRAINING_PACK_MODEL`).

- Много блоков ниже порога:
  - увеличьте `questions_per_block`;
  - улучшите промпт;
  - проверьте слишком агрессивный дедуп;
  - используйте `fill-training-pack.py` с несколькими раундами.

- LLM отвечает мусором/не JSON:
  - смотрите `training_pack/runs/*/*.raw.json`;
  - ужесточайте системный промпт;
  - используйте более стабильную модель.

- Генерация «долго висит» до первого вывода:
  - для больших моделей это нормально (долгий prefill);
  - уменьшайте `questions_per_block` (например 3..5);
  - проверяйте keep-alive и что модель уже прогрета.

