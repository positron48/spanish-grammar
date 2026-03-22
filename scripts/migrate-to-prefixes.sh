#!/bin/bash

# Главный скрипт для миграции к системе с числовыми префиксами
# Использование: ./scripts/migrate-to-prefixes.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 МИГРАЦИЯ: Добавление числовых префиксов к папкам глав"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Шаг 1: Переименование папок
echo "Шаг 1: Переименование папок глав..."
bash "$SCRIPT_DIR/add-chapter-prefixes.sh"
echo ""

# Шаг 2: Обновление путей в generation-status.json
echo "Шаг 2: Обновление путей в generation-status.json..."
bash "$SCRIPT_DIR/update-paths-after-prefix.sh"
echo ""

# Шаг 3: Обновление индексов
echo "Шаг 3: Обновление индексов глав..."
if command -v node &> /dev/null; then
    echo "  Обновление admin/data/chapters-index.json..."
    node "$PROJECT_ROOT/admin/generate-index.js" || echo "  ⚠️  Предупреждение: не удалось обновить admin индекс"
    
    echo "  Обновление test/data/chapters-index.json..."
    node "$PROJECT_ROOT/test/scripts/generate-chapters-index.js" || echo "  ⚠️  Предупреждение: не удалось обновить test индекс"
else
    echo "  ⚠️  Node.js не найден, пропускаем обновление индексов"
    echo "     Запустите вручную:"
    echo "       node admin/generate-index.js"
    echo "       node test/scripts/generate-chapters-index.js"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ МИГРАЦИЯ ЗАВЕРШЕНА"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Все папки глав теперь имеют числовые префиксы (001., 002., ...)"
echo "Все скрипты и системы обновлены для работы с префиксами."
echo ""
echo "Проверьте результат:"
echo "  - Папки в chapters/ должны иметь формат: 001.chapter_id"
echo "  - config/generation-status.json должен содержать обновленные пути"
echo "  - Индексы должны быть обновлены"
echo ""
