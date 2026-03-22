#!/bin/bash

# Скрипт для обновления путей в generation-status.json после добавления префиксов
# Использование: ./scripts/update-paths-after-prefix.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATUS_FILE="$PROJECT_ROOT/config/generation-status.json"
CHAPTERS_DIR="$PROJECT_ROOT/chapters"

if [ ! -f "$STATUS_FILE" ]; then
    echo "Ошибка: не найден $STATUS_FILE"
    exit 1
fi

echo "📝 Обновление путей в generation-status.json..."
echo ""

# Создаем резервную копию
cp "$STATUS_FILE" "$STATUS_FILE.backup"
echo "✓ Создана резервная копия: $STATUS_FILE.backup"

# Временный файл для обновленного JSON
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

# Используем Python для обновления путей
python3 << PYTHON_SCRIPT
import json
import sys

with open('$STATUS_FILE', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Сортируем главы по order и создаем мапу order -> порядковый номер
chapters_sorted = sorted(data['chapters'], key=lambda x: x.get('order', 0))
order_to_seq = {}
for idx, ch in enumerate(chapters_sorted, 1):
    order = ch.get('order', 0)
    order_to_seq[order] = idx

# Обновляем пути для каждой главы
for ch in data['chapters']:
    order = ch.get('order', 0)
    chapter_id = ch.get('chapter_id', '')
    
    # Получаем порядковый номер
    seq = order_to_seq.get(order, 0)
    prefix = f"{seq:03d}"
    
    # Новое имя папки
    new_dir_name = f"{prefix}.{chapter_id}"
    new_output_dir = f"chapters/{new_dir_name}"
    
    # Обновляем output_dir
    ch['output_dir'] = new_output_dir
    
    # Обновляем пути в files
    if 'files' in ch:
        ch['files']['outline'] = f"{new_output_dir}/01-outline.json"
        ch['files']['theory_blocks'] = f"{new_output_dir}/02-theory-blocks/"
        ch['files']['questions'] = f"{new_output_dir}/03-questions.json"
        ch['files']['inline_quizzes'] = f"{new_output_dir}/04-inline-quizzes.json"
        ch['files']['final'] = f"{new_output_dir}/05-final.json"
        ch['files']['validation'] = f"{new_output_dir}/05-validation.json"

# Сохраняем обновленный JSON
with open('$TEMP_FILE', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("✓ Пути обновлены")
PYTHON_SCRIPT

# Заменяем оригинальный файл
mv "$TEMP_FILE" "$STATUS_FILE"

echo ""
echo "✓ Обновление завершено"
echo "  Резервная копия сохранена в: $STATUS_FILE.backup"
