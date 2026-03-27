#!/bin/bash

# Вспомогательный скрипт для подготовки генерации главы/курса
# Создает структуру директорий и выводит команды для Cursor

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE="${1:-chapter}"
CHAPTER_ID="${2:-}"

case "$MODE" in
    chapter)
        if [ -z "$CHAPTER_ID" ]; then
            echo "Ошибка: укажите chapter_id"
            echo "Использование: $0 chapter <chapter_id>"
            echo "Пример: $0 chapter es.grammar.past_preterito_perfecto.haber_participio_form"
            exit 1
        fi
        
        # Подключаем утилиты для работы с именами папок
        source "$SCRIPT_DIR/chapter-utils.sh"
        
        # Получаем путь к папке главы (может быть с префиксом или без)
        CHAPTER_DIR=$(get_chapter_dir "$CHAPTER_ID" "$PROJECT_ROOT/chapters")
        if [ $? -ne 0 ]; then
            # Если папка не найдена, создаем новую (без префикса, префикс добавится позже)
            CHAPTER_DIR="$PROJECT_ROOT/chapters/$CHAPTER_ID"
        fi
        
        INPUT_FILE="$PROJECT_ROOT/config/chapter-templates/$CHAPTER_ID-input.json"
        
        # Создаем структуру
        mkdir -p "$CHAPTER_DIR/02-theory-blocks" "$(dirname "$INPUT_FILE")"
        
        # Создаем шаблон входного файла если его нет
        if [ ! -f "$INPUT_FILE" ]; then
            cat > "$INPUT_FILE" <<EOF
{
  "chapter_input": {
    "chapter_id": "$CHAPTER_ID",
    "section_id": "REPLACE_WITH_SECTION_ID",
    "title": "REPLACE_WITH_TITLE",
    "level": "A1",
    "ui_language": "ru",
    "target_language": "es",
    "prerequisites": []
  }
}
EOF
            echo "✓ Создан шаблон входного файла: $INPUT_FILE"
            echo "⚠️  Заполните $INPUT_FILE перед генерацией"
        fi
        
        echo ""
        echo "📝 Команда для Cursor:"
        echo ""
        echo "@prompts/00-generate-full-chapter.md @$INPUT_FILE @02-chapter-schema.json"
        echo ""
        echo "Выполни полную генерацию главы $CHAPTER_ID согласно мастер-промпту."
        echo "Выполни все 5 проходов последовательно и проверь результат валидации."
        echo ""
        ;;
        
    course)
        SECTIONS_FILE="$PROJECT_ROOT/01-sections.md"
        
        if [ ! -f "$SECTIONS_FILE" ]; then
            echo "Ошибка: не найден $SECTIONS_FILE"
            exit 1
        fi
        
        echo "📚 Генерация всего курса"
        echo ""
        echo "📝 Команда для Cursor:"
        echo ""
        echo "@prompts/00-generate-full-course.md @$SECTIONS_FILE @02-chapter-schema.json @prompts/00-generate-full-chapter.md"
        echo ""
        echo "Выполни полную генерацию всего курса согласно мастер-промпту:"
        echo "1. Извлеки список глав из 01-sections.md"
        echo "2. Создай входные файлы для каждой главы (если их нет)"
        echo "3. Генерируй все главы последовательно"
        echo "4. Собери манифест курса"
        echo ""
        ;;
        
    *)
        echo "Использование: $0 {chapter|course} [chapter_id]"
        echo ""
        echo "Примеры:"
        echo "  $0 chapter es.grammar.past_preterito_perfecto.haber_participio_form"
        echo "  $0 course"
        exit 1
        ;;
esac
