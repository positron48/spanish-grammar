#!/bin/bash

# Скрипт для создания входных файлов глав из 01-sections.md
# Использование: ./scripts/create-chapter-inputs.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SECTIONS_FILE="$PROJECT_ROOT/01-sections.md"
TEMPLATES_DIR="$PROJECT_ROOT/config/chapter-templates"

mkdir -p "$TEMPLATES_DIR"

echo "📝 Создание входных файлов глав из $SECTIONS_FILE..."
echo ""
echo "Этот скрипт подготовит структуру. Фактическое создание файлов будет выполнено Cursor."
echo "См. prompts/00-prepare-chapter-inputs.md для инструкций."
echo ""
