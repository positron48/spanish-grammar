#!/bin/bash

# Скрипт для добавления числовых префиксов к папкам глав
# Использование: ./scripts/add-chapter-prefixes.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATUS_FILE="$PROJECT_ROOT/config/generation-status.json"
CHAPTERS_DIR="$PROJECT_ROOT/chapters"

if [ ! -f "$STATUS_FILE" ]; then
    echo "Ошибка: не найден $STATUS_FILE"
    exit 1
fi

if [ ! -d "$CHAPTERS_DIR" ]; then
    echo "Ошибка: директория $CHAPTERS_DIR не найдена"
    exit 1
fi

echo "📝 Добавление числовых префиксов к папкам глав..."
echo ""

# Временная директория для переименований
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Извлекаем все главы из generation-status.json и сортируем по order
jq -r '.chapters | sort_by(.order) | .[] | "\(.order|tostring)|\(.chapter_id)"' "$STATUS_FILE" > "$TEMP_DIR/chapters_list.txt"

# Счетчик для последовательной нумерации (001, 002, ...)
counter=1

while IFS='|' read -r order chapter_id; do
    # Форматируем номер с ведущими нулями (001, 002, ...)
    prefix=$(printf "%03d" $counter)
    
    old_path="$CHAPTERS_DIR/$chapter_id"
    new_name="${prefix}.${chapter_id}"
    new_path="$CHAPTERS_DIR/$new_name"
    
    if [ -d "$old_path" ]; then
        # Проверяем, не переименована ли уже папка
        if [ "$(basename "$old_path")" != "$new_name" ]; then
            echo "  Переименование: $(basename "$old_path") -> $new_name"
            mv "$old_path" "$new_path"
        else
            echo "  ✓ Уже переименовано: $new_name"
        fi
    else
        # Проверяем, может быть папка уже с префиксом
        if [ -d "$new_path" ]; then
            echo "  ✓ Уже существует: $new_name"
        else
            echo "  ⚠️  Папка не найдена: $chapter_id (пропущено)"
        fi
    fi
    
    counter=$((counter + 1))
done < "$TEMP_DIR/chapters_list.txt"

echo ""
echo "✓ Переименование завершено"
echo ""
echo "⚠️  ВАЖНО: Теперь нужно обновить:"
echo "  1. config/generation-status.json (пути к папкам)"
echo "  2. Все скрипты для работы с префиксами"
echo ""
echo "Запустите: ./scripts/update-paths-after-prefix.sh"
