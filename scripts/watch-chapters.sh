#!/bin/bash

# Скрипт для мониторинга изменений в папке chapters и автоматического обновления индексов
# Использование: ./scripts/watch-chapters.sh [admin|test|both] [--rebuild-final]

# Не завершаем скрипт при ошибках, чтобы мониторинг продолжал работать
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WATCH_MODE="${1:-both}"
REBUILD_FINAL=false

# Проверяем флаг --rebuild-final
if [[ "$*" == *"--rebuild-final"* ]]; then
    REBUILD_FINAL=true
fi

# Проверяем наличие inotifywait
if ! command -v inotifywait >/dev/null 2>&1; then
    echo "⚠️  inotifywait не найден. Установите inotify-tools:"
    echo "   sudo apt install inotify-tools"
    echo ""
    echo "Без inotifywait автоматическое обновление индексов работать не будет."
    echo "Индексы будут обновляться только при перезапуске сервера."
    exit 0
fi

# Функция обновления индекса админ-панели
update_admin_index() {
    if [ -f "$PROJECT_ROOT/admin/generate-index.js" ]; then
        if node "$PROJECT_ROOT/admin/generate-index.js" >/dev/null 2>&1; then
            echo "[$(date +%H:%M:%S)] ✓ Индекс админ-панели обновлен"
        else
            echo "[$(date +%H:%M:%S)] ✗ Ошибка обновления индекса админ-панели"
        fi
    fi
}

# Функция обновления индекса тестовой системы
update_test_index() {
    if [ -f "$PROJECT_ROOT/test/scripts/generate-chapters-index.js" ]; then
        if node "$PROJECT_ROOT/test/scripts/generate-chapters-index.js" >/dev/null 2>&1; then
            echo "[$(date +%H:%M:%S)] ✓ Индекс тестовой системы обновлен"
        else
            echo "[$(date +%H:%M:%S)] ✗ Ошибка обновления индекса тестовой системы"
        fi
    fi
}

# Функция пересборки final.json для главы (с debounce)
rebuild_chapter_final() {
    local chapter_dir="$1"
    local chapter_id=""
    
    # Извлекаем chapter_id из пути
    local folder_name=$(basename "$chapter_dir")
    if [[ "$folder_name" =~ ^[0-9]{3}\.(.+)$ ]]; then
        chapter_id="${BASH_REMATCH[1]}"
    else
        chapter_id="$folder_name"
    fi
    
    if [ -z "$chapter_id" ]; then
        return
    fi
    
    # Используем временный файл для debounce (избегаем множественных пересборок)
    local lock_file="/tmp/rebuild_final_${chapter_id//\//_}.lock"
    local current_time=$(date +%s)
    local last_time=0
    
    # Читаем время последней пересборки
    if [ -f "$lock_file" ]; then
        last_time=$(cat "$lock_file" 2>/dev/null || echo "0")
    fi
    
    # Проверяем, прошло ли достаточно времени (debounce 2 секунды)
    local time_diff=$((current_time - last_time))
    if [ $time_diff -lt 2 ]; then
        return
    fi
    
    # Сохраняем время текущей пересборки
    echo "$current_time" > "$lock_file"
    
    # Пересобираем final.json для этой главы
    if bash "$PROJECT_ROOT/scripts/assemble-chapter.sh" "$chapter_id" >/dev/null 2>&1; then
        echo "[$(date +%H:%M:%S)] ✓ Пересобран final.json: $chapter_id"
    else
        echo "[$(date +%H:%M:%S)] ✗ Ошибка пересборки final.json: $chapter_id"
    fi
}

# Функция обработки изменений
handle_change() {
    local event_file="$1"
    local event_type="$2"
    
    # Игнорируем временные файлы
    if [[ "$event_file" == *.tmp ]] || [[ "$event_file" == *~ ]] || [[ "$event_file" == .* ]]; then
        return
    fi
    
    # Игнорируем 05-final.json: это наш артефакт от assemble-chapter.sh,
    # индексы уже обновлены до пересборки — не дублируем обновления
    if [[ "$event_file" == *"05-final.json"* ]]; then
        return
    fi
    
    # Проверяем, нужно ли обновить индексы
    local should_update_index=false
    local should_rebuild_final=false
    local chapter_dir=""
    
    # Проверяем изменения в ключевых файлах глав
    if [[ "$event_file" == *"01-outline.json"* ]] || \
       [[ "$event_file" == *"03-questions.json"* ]] || \
       [[ "$event_file" == *"02-theory-blocks"* ]]; then
        should_update_index=true
        if [ "$REBUILD_FINAL" = true ]; then
            should_rebuild_final=true
            # Извлекаем путь к папке главы
            # Если это файл в 02-theory-blocks, берем родительскую папку
            if [[ "$event_file" == *"02-theory-blocks"* ]]; then
                chapter_dir=$(dirname "$(dirname "$event_file")")
            else
                chapter_dir=$(dirname "$event_file")
            fi
        fi
    fi
    
    # Проверяем создание/перемещение папок глав
    if [[ "$event_type" == *"CREATE"* ]] && [[ "$event_type" == *"ISDIR"* ]]; then
        should_update_index=true
        chapter_dir="$event_file"
    fi
    if [[ "$event_type" == *"MOVED_TO"* ]] && [[ "$event_type" == *"ISDIR"* ]]; then
        should_update_index=true
        chapter_dir="$event_file"
    fi
    
    # Обновляем индексы
    if [ "$should_update_index" = true ]; then
        case "$WATCH_MODE" in
            admin)
                update_admin_index
                ;;
            test)
                update_test_index
                ;;
            both)
                update_admin_index
                update_test_index
                ;;
        esac
    fi
    
    # Пересобираем final.json если нужно (debounce внутри функции)
    if [ "$should_rebuild_final" = true ] && [ -n "$chapter_dir" ]; then
        rebuild_chapter_final "$chapter_dir"
    fi
}

# Переходим в корень проекта
cd "$PROJECT_ROOT" || exit 1

# Обработка сигналов для корректного завершения
trap 'exit 0' INT TERM

# Мониторим папку chapters на изменения
inotifywait -m -r -e create,modify,moved_to,delete \
    --format '%w%f %e' \
    "$PROJECT_ROOT/chapters" 2>/dev/null | while read -r line; do
    
    # Парсим вывод inotifywait
    event_file=$(echo "$line" | cut -d' ' -f1)
    event_type=$(echo "$line" | cut -d' ' -f2-)
    
    handle_change "$event_file" "$event_type"
done
