#!/bin/bash

# Скрипт для сборки финального JSON главы из промежуточных файлов
# Использование: ./scripts/assemble-chapter.sh <chapter_id>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHAPTER_ID="${1:-}"

# Подключаем утилиты для работы с именами папок
source "$SCRIPT_DIR/chapter-utils.sh"

if [ -z "$CHAPTER_ID" ]; then
    echo "Ошибка: укажите chapter_id"
    echo "Использование: $0 <chapter_id>"
    exit 1
fi

# Получаем путь к папке главы (может быть с префиксом или без)
CHAPTER_DIR=$(get_chapter_dir "$CHAPTER_ID" "$PROJECT_ROOT/chapters")
if [ $? -ne 0 ]; then
    echo "Ошибка: папка главы не найдена: $CHAPTER_ID"
    exit 1
fi
SCHEMA_FILE="$PROJECT_ROOT/02-chapter-schema.json"

# Проверяем наличие необходимых файлов
OUTLINE_FILE="$CHAPTER_DIR/01-outline.json"
QUESTIONS_FILE="$CHAPTER_DIR/03-questions.json"

if [ ! -f "$OUTLINE_FILE" ]; then
    echo "Ошибка: не найден $OUTLINE_FILE"
    exit 1
fi

if [ ! -f "$QUESTIONS_FILE" ]; then
    echo "Ошибка: не найден $QUESTIONS_FILE"
    exit 1
fi

# Создаем директорию для блоков если её нет
THEORY_BLOCKS_DIR="$CHAPTER_DIR/02-theory-blocks"
mkdir -p "$THEORY_BLOCKS_DIR"

# Временные файлы
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Собираем финальный JSON
FINAL_FILE="$CHAPTER_DIR/05-final.json"

echo "Сборка финального JSON из промежуточных файлов..."

# Собираем theory_blocks
if [ "$(ls -A "$THEORY_BLOCKS_DIR"/*.json 2>/dev/null)" ]; then
    # Объединяем все theory_blocks в массив
    jq -s 'map(.theory_block)' "$THEORY_BLOCKS_DIR"/*.json > "$TEMP_DIR/theory_blocks.json"
else
    echo "⚠️  Предупреждение: нет theory_blocks файлов в $THEORY_BLOCKS_DIR"
    echo '[]' > "$TEMP_DIR/theory_blocks.json"
fi

# Читаем outline
OUTLINE_JSON=$(cat "$OUTLINE_FILE")

# Читаем theory_blocks
THEORY_BLOCKS_JSON=$(cat "$TEMP_DIR/theory_blocks.json")

# Формируем blocks: theory + inline_quizzes (динамически из вопросов)
# Для каждого theory блока создаем quiz_inline с первыми 2 вопросами
jq -s '
  .[0] as $outline |
  .[1] as $theory_blocks |
  .[2] as $questions |
  
  # Получаем все вопросы
  (if $questions.questions then $questions.questions else [] end) as $all_questions |
  
  # Формируем blocks
  # $theory_blocks уже содержит массив theory_block объектов (после map(.theory_block))
  $theory_blocks | map(.id as $block_id | {
    id: $block_id,
    type: "theory",
    title: (if .content_md then (.content_md | split("\n")[0] | gsub("^#+ *"; "") | gsub("\\*\\*"; "")) else "" end),
    theory: {
      concept_id: .concept_id,
      content_md: .content_md,
      key_points: (if .key_points then .key_points else [] end),
      common_mistakes: (if .common_mistakes then .common_mistakes else [] end),
      examples: (if .examples then .examples else [] end)
    }
  }) as $theory_blocks_formatted |
  
  # Добавляем inline_quizzes после каждого theory блока
  # Берем первые 2 вопроса для каждого theory_block_id
  (reduce range(0; $theory_blocks_formatted | length) as $i (
    [];
    . + [$theory_blocks_formatted[$i]] +
    # Находим вопросы для этого theory блока и берем первые 2
    (($all_questions | map(select(.theory_block_id == $theory_blocks_formatted[$i].id)) | .[0:2] | map(.id)) as $quiz_question_ids |
     if ($quiz_question_ids | length) > 0 then
       # Формируем ID для quiz блока
       # Извлекаем номер из theory блока (формат: b{N}_...)
       (($theory_blocks_formatted[$i].id | capture("^b(?<num>[0-9]+)_")) as $match |
        if $match then
          [{
            id: "b\($match.num | tonumber + 1)_quiz_after_block",
            type: "quiz_inline",
            title: "Проверка знаний",
            quiz_inline: {
              question_ids: $quiz_question_ids,
              show_answers_immediately: true
            }
          }]
        else
          # Fallback: если формат не совпадает, используем простой формат
          [{
            id: "b\($i + 1)_quiz_after_block",
            type: "quiz_inline",
            title: "Проверка знаний",
            quiz_inline: {
              question_ids: $quiz_question_ids,
              show_answers_immediately: true
            }
          }]
        end)
     else [] end)
  ))
' "$OUTLINE_FILE" "$TEMP_DIR/theory_blocks.json" "$QUESTIONS_FILE" > "$TEMP_DIR/blocks.json"

# Сохраняем старый updated_at, если файл существует
OLD_UPDATED_AT=""
if [ -f "$FINAL_FILE" ]; then
    OLD_UPDATED_AT=$(jq -r '.meta.updated_at // empty' "$FINAL_FILE" 2>/dev/null || echo "")
fi

# Собираем новый финальный JSON во временный файл
# Исключаем первые 2 вопроса каждого theory блока из финального теста
jq -s '
  .[0].chapter_outline as $outline |
  .[1] as $blocks |
  .[2] as $questions |
  .[3] as $theory_blocks |
  
  # Получаем все вопросы
  (if $questions.questions then $questions.questions else [] end) as $all_questions |
  
  # Находим ID первых 2 вопросов для каждого theory блока
  ($theory_blocks | map(.id) | map(. as $block_id |
    ($all_questions | map(select(.theory_block_id == $block_id)) | .[0:2] | map(.id))
  ) | add) as $excluded_question_ids |
  
  {
    schema_version: "1.0.0",
    id: $outline.chapter_id,
    section_id: $outline.section_id,
    title: $outline.title,
    title_translations: (if $outline.title_translations then $outline.title_translations else {} end),
    title_short: (if $outline.title_short then $outline.title_short else $outline.title end),
    description: $outline.description,
    ui_language: $outline.ui_language,
    target_language: $outline.target_language,
    level: $outline.level,
    order: (if $outline.order then $outline.order else 0 end),
    prerequisites: (if $outline.prerequisites then $outline.prerequisites else [] end),
    concept_refs: (if $outline.concept_refs then $outline.concept_refs else [] end),
    learning_objectives: (if $outline.learning_objectives then $outline.learning_objectives else [] end),
    estimated_minutes: (if $outline.estimated_minutes then $outline.estimated_minutes else 30 end),
    blocks: $blocks,
    question_bank: {
      questions: $all_questions
    },
    chapter_test: {
      num_questions: 10,
      pool_question_ids: ($all_questions | map(.id) | map(select(. as $id | ($excluded_question_ids | index($id) | not)))),
      selection_strategy: {
        type: "stratified_by_theory_block",
        min_per_theory_block: 1,
        avoid_recent_window: 30,
        difficulty_mix: {
          easy: 3,
          medium: 5,
          hard: 2
        }
      }
    },
    meta: {
      version: "2026.01.16",
      updated_at: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
      source: "llm"
    }
  }
' "$OUTLINE_FILE" "$TEMP_DIR/blocks.json" "$QUESTIONS_FILE" "$TEMP_DIR/theory_blocks.json" > "$TEMP_DIR/new_final.json"

# Проверяем, были ли изменения (сравниваем JSON, исключая meta.updated_at)
if [ -f "$FINAL_FILE" ] && [ -n "$OLD_UPDATED_AT" ]; then
    # Удаляем meta.updated_at из обоих файлов для сравнения
    jq 'del(.meta.updated_at)' "$FINAL_FILE" > "$TEMP_DIR/old_without_updated.json"
    jq 'del(.meta.updated_at)' "$TEMP_DIR/new_final.json" > "$TEMP_DIR/new_without_updated.json"
    
    # Сравниваем JSON (игнорируя различия в пробелах)
    if diff -q <(jq -cS '.' "$TEMP_DIR/old_without_updated.json") <(jq -cS '.' "$TEMP_DIR/new_without_updated.json") >/dev/null 2>&1; then
        # Нет изменений - используем старый updated_at
        jq --arg old_updated_at "$OLD_UPDATED_AT" '.meta.updated_at = $old_updated_at' "$TEMP_DIR/new_final.json" > "$FINAL_FILE"
        echo "✓ Финальный JSON собран (без изменений, updated_at сохранен): $FINAL_FILE"
    else
        # Есть изменения - используем новый updated_at
        cp "$TEMP_DIR/new_final.json" "$FINAL_FILE"
        echo "✓ Финальный JSON собран (обновлен): $FINAL_FILE"
    fi
else
    # Файл не существовал - просто копируем новый
    cp "$TEMP_DIR/new_final.json" "$FINAL_FILE"
    echo "✓ Финальный JSON собран: $FINAL_FILE"
fi

# Проверяем соответствие схеме (если установлен ajv-cli)
if command -v ajv &> /dev/null; then
    echo "Проверка соответствия схеме..."
    if ajv validate -s "$SCHEMA_FILE" -d "$FINAL_FILE" 2>/dev/null; then
        echo "✓ JSON соответствует схеме"
    else
        echo "⚠️  Предупреждение: JSON может не соответствовать схеме"
    fi
else
    echo "⚠️  ajv-cli не установлен, пропускаем проверку схемы"
fi

# Краткая статистика
echo ""
echo "Статистика главы:"
jq '{
  theory_blocks: ((.blocks // []) | map(select(.type == "theory")) | length),
  inline_quizzes: ((.blocks // []) | map(select(.type == "quiz_inline")) | length),
  total_questions: ((.question_bank.questions // []) | length),
  chapter_test_pool: ((.chapter_test.pool_question_ids // []) | length)
}' "$FINAL_FILE" 2>/dev/null || echo "  (не удалось получить статистику)"
