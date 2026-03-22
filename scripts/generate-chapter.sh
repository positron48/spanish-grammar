#!/bin/bash

# Скрипт для генерации главы курса по этапам
# Использование: ./scripts/generate-chapter.sh <chapter_id> [--step N]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHAPTER_ID="${1:-}"
STEP="${2:-all}"

# Подключаем утилиты для работы с именами папок
source "$SCRIPT_DIR/chapter-utils.sh"

if [ -z "$CHAPTER_ID" ]; then
    echo "Ошибка: укажите chapter_id"
    echo "Использование: $0 <chapter_id> [--step N]"
    echo "Пример: $0 en.grammar.present_perfect.experience --step 1"
    exit 1
fi

# Получаем путь к папке главы (может быть с префиксом или без)
CHAPTER_DIR=$(get_chapter_dir "$CHAPTER_ID" "$PROJECT_ROOT/chapters")
if [ $? -ne 0 ]; then
    # Если папка не найдена, создаем новую (без префикса, префикс добавится позже)
    CHAPTER_DIR="$PROJECT_ROOT/chapters/$CHAPTER_ID"
fi
CONFIG_FILE="$PROJECT_ROOT/config/generation-config.json"
SCHEMA_FILE="$PROJECT_ROOT/02-chapter-schema.json"

# Создаем директорию для главы
mkdir -p "$CHAPTER_DIR/02-theory-blocks" "$CHAPTER_DIR/logs"

# Скрипт используется только для создания структуры директорий и подготовки файлов
# Генерация контента выполняется напрямую в Cursor IDE с использованием промптов из prompts/

echo "📝 Этот скрипт используется для создания структуры директорий."
echo "Для генерации контента используйте промпты из prompts/ напрямую в Cursor."
echo "См. CURSOR-WORKFLOW.md для подробных инструкций."

# Проход 1: План главы
run_step_1() {
    echo "=== Проход 1: Генерация плана главы ==="
    
    INPUT_FILE="$PROJECT_ROOT/config/chapter-templates/$CHAPTER_ID-input.json"
    if [ ! -f "$INPUT_FILE" ]; then
        echo "Создаю шаблон входного файла: $INPUT_FILE"
        mkdir -p "$(dirname "$INPUT_FILE")"
        cat > "$INPUT_FILE" <<EOF
{
  "chapter_input": {
    "chapter_id": "$CHAPTER_ID",
    "section_id": "REPLACE_WITH_SECTION_ID",
    "title": "REPLACE_WITH_TITLE",
    "level": "B1",
    "ui_language": "ru",
    "target_language": "en"
  }
}
EOF
        echo "⚠️  Заполните $INPUT_FILE и запустите снова"
        exit 1
    fi
    
    OUTPUT_FILE="$CHAPTER_DIR/01-outline.json"
    PROMPT_FILE="$PROJECT_ROOT/prompts/01-plan.md"
    
    echo ""
    echo "Для генерации плана главы:"
    echo "1. Откройте Cursor и используйте @$PROMPT_FILE и @$INPUT_FILE"
    echo "2. Попросите Cursor сгенерировать план согласно промпту"
    echo "3. Сохраните результат в $OUTPUT_FILE"
    echo ""
    echo "Пример запроса в Cursor:"
    echo "  @$PROMPT_FILE @$INPUT_FILE"
    echo "  Используй промпт из prompts/01-plan.md и входные данные из config/chapter-templates/$CHAPTER_ID-input.json"
    echo "  Сгенерируй план главы в формате JSON. Сохрани в $OUTPUT_FILE"
    echo ""
    
    # Создаем пустой файл-заглушку для структуры
    echo '{}' > "$OUTPUT_FILE"
}

# Проход 2: Теория по блокам
run_step_2() {
    echo "=== Проход 2: Генерация theory blocks ==="
    
    OUTLINE_FILE="$CHAPTER_DIR/01-outline.json"
    if [ ! -f "$OUTLINE_FILE" ]; then
        echo "Ошибка: сначала выполните проход 1 (создайте $OUTLINE_FILE)"
        exit 1
    fi
    
    PROMPT_FILE="$PROJECT_ROOT/prompts/02-theory-block.md"
    THEORY_BLOCKS_DIR="$CHAPTER_DIR/02-theory-blocks"
    
    echo ""
    echo "Для генерации theory blocks:"
    echo "1. Проверьте список блоков в $OUTLINE_FILE"
    echo "2. Для каждого блока используйте @$PROMPT_FILE и @$OUTLINE_FILE"
    echo ""
    
    # Извлекаем список theory_blocks из плана
    if jq empty "$OUTLINE_FILE" 2>/dev/null; then
        BLOCK_COUNT=$(jq '.chapter_outline.theory_blocks | length' "$OUTLINE_FILE" 2>/dev/null || echo "0")
        echo "Найдено блоков: $BLOCK_COUNT"
        
        jq -r '.chapter_outline.theory_blocks[] | .id' "$OUTLINE_FILE" 2>/dev/null | while read -r block_id; do
            OUTPUT_FILE="$THEORY_BLOCKS_DIR/$block_id.json"
            echo ""
            echo "Блок: $block_id"
            echo "  Промпт: @$PROMPT_FILE"
            echo "  Данные: @$OUTLINE_FILE (block_id: $block_id)"
            echo "  Результат: $OUTPUT_FILE"
            echo '{}' > "$OUTPUT_FILE"
        done
    else
        echo "⚠️  Сначала выполните проход 1 для создания $OUTLINE_FILE"
    fi
    
    echo ""
    echo "Пример запроса в Cursor для блока:"
    echo "  @$PROMPT_FILE @$OUTLINE_FILE"
    echo "  Используй промпт из prompts/02-theory-block.md и данные блока {block_id} из $OUTLINE_FILE"
    echo "  Сгенерируй theory_block. Сохрани в $THEORY_BLOCKS_DIR/{block_id}.json"
}

# Проход 3: Банк вопросов
run_step_3() {
    echo "=== Проход 3: Генерация банка вопросов ==="
    
    OUTLINE_FILE="$CHAPTER_DIR/01-outline.json"
    if [ ! -f "$OUTLINE_FILE" ]; then
        echo "Ошибка: сначала выполните проход 1"
        exit 1
    fi
    
    PROMPT_FILE="$PROJECT_ROOT/prompts/03-questions.md"
    OUTPUT_FILE="$CHAPTER_DIR/03-questions.json"
    THEORY_BLOCKS_DIR="$CHAPTER_DIR/02-theory-blocks"
    
    echo ""
    echo "Для генерации банка вопросов:"
    echo "1. Используйте @$PROMPT_FILE"
    echo "2. Используйте @$OUTLINE_FILE (план)"
    echo "3. Используйте все файлы из @$THEORY_BLOCKS_DIR/"
    echo ""
    echo "Пример запроса в Cursor:"
    echo "  @$PROMPT_FILE @$OUTLINE_FILE @$THEORY_BLOCKS_DIR/"
    echo "  Используй промпт из prompts/03-questions.md"
    echo "  Используй план из $OUTLINE_FILE и все theory_blocks из $THEORY_BLOCKS_DIR/"
    echo "  Сгенерируй question_bank с минимум 60 вопросами. Сохрани в $OUTPUT_FILE"
    echo ""
    
    echo '{"questions": []}' > "$OUTPUT_FILE"
}

# Проход 4: Inline quizzes (теперь генерируются автоматически)
run_step_4() {
    echo "=== Проход 4: Inline quizzes ==="
    echo ""
    echo "✓ Inline quizzes теперь генерируются автоматически при сборке финального файла"
    echo "  Квизы создаются динамически из первых 2 вопросов каждого theory блока"
    echo "  Файл 04-inline-quizzes.json больше не используется"
    echo ""
}

# Проход 5: Сборка финального JSON и валидация
run_step_5() {
    echo "=== Проход 5: Сборка и валидация финального JSON ==="
    
    OUTLINE_FILE="$CHAPTER_DIR/01-outline.json"
    QUESTIONS_FILE="$CHAPTER_DIR/03-questions.json"
    
    if [ ! -f "$OUTLINE_FILE" ] || [ ! -f "$QUESTIONS_FILE" ]; then
        echo "Ошибка: сначала выполните проходы 1 и 3"
        exit 1
    fi
    
    # Собираем финальный JSON (упрощенная версия, нужно улучшить)
    FINAL_FILE="$CHAPTER_DIR/05-final.json"
    
    echo "Сборка финального JSON..."
    # TODO: Реализовать полную сборку из всех частей
    
    # Валидация
    VALIDATION_PROMPT="$PROJECT_ROOT/prompts/05-validation.md"
    VALIDATION_OUTPUT="$CHAPTER_DIR/05-validation.json"
    SCHEMA_FILE="$PROJECT_ROOT/02-chapter-schema.json"
    
    echo ""
    echo "Для валидации главы:"
    echo "1. Используйте @$VALIDATION_PROMPT"
    echo "2. Используйте @$FINAL_FILE (финальный JSON)"
    echo "3. Используйте @$SCHEMA_FILE (схема)"
    echo ""
    echo "Пример запроса в Cursor:"
    echo "  @$VALIDATION_PROMPT @$FINAL_FILE @$SCHEMA_FILE"
    echo "  Используй промпт из prompts/05-validation.md"
    echo "  Проверь $FINAL_FILE на соответствие схеме $SCHEMA_FILE"
    echo "  Выполни все проверки из промпта. Сохрани результат в $VALIDATION_OUTPUT"
    echo ""
    
    echo '{"validation_result": {"is_valid": false}}' > "$VALIDATION_OUTPUT"
}

# Главная логика
case "$STEP" in
    --step 1|1)
        run_step_1
        ;;
    --step 2|2)
        run_step_2
        ;;
    --step 3|3)
        run_step_3
        ;;
    --step 4|4)
        run_step_4
        ;;
    --step 5|5)
        run_step_5
        ;;
    all|--step all)
        run_step_1
        run_step_2
        run_step_3
        run_step_4
        run_step_5
        echo ""
        echo "=== Генерация завершена ==="
        echo "Результаты в: $CHAPTER_DIR"
        ;;
    *)
        echo "Неизвестный шаг: $STEP"
        echo "Использование: $0 <chapter_id> [--step N|all]"
        exit 1
        ;;
esac
