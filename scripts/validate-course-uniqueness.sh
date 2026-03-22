#!/bin/bash

# Скрипт для проверки уникальности вопросов по всему курсу
# Использование: ./scripts/validate-course-uniqueness.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Проверка уникальности вопросов по всему курсу отключена (по запросу).
echo "Проверка уникальности вопросов по всему курсу: отключена"
exit 0

# Подключаем утилиты для работы с именами папок
source "$SCRIPT_DIR/chapter-utils.sh"

# Находим все главы
CHAPTERS=$(find "$PROJECT_ROOT/chapters" -mindepth 1 -maxdepth 1 -type d -not -name '.*' | while read dir; do
    chapter_name=$(basename "$dir")
    # Убираем префикс вида 001.
    chapter_id=$(echo "$chapter_name" | sed 's|^[0-9][0-9][0-9]\.||')
    echo "$chapter_id"
done | sort -u)

# Запускаем Python скрипт проверки уникальности
python3 << PYTHON_SCRIPT
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = '$PROJECT_ROOT'
chapters_dir = Path(PROJECT_ROOT) / 'chapters'

# Паттерны, которые могут повторяться
ALLOWED_DUPLICATE_PREFIXES = [
    'Выберите правильный вариант:',
    'Выберите правильный вариант.',
    'Выберите правильный императив:',
    'Выберите правильное отрицательное предложение:',
    'Выберите правильное предложение:',
    'Выберите правильное предложение.',
    'Выберите правильный вариант предложения:',
    'Выберите правильный вариант вопроса:',
    'Выберите правильный вопрос:',
    'Выберите правильный вариант отрицания:',
    'Выберите правильное отрицание:',
    'Выберите правильный вопрос о текущем действии:',
    'Выберите правильный вопрос о привычках:',
    'Выберите правильный вариант для выражения существования книги на столе:',
    'Выберите правильное предложение с наречием частоты:',
    'Выберите правильный порядок слов:',
    'Выберите правильный порядок слов в вопросе:',
]

ALLOWED_DUPLICATE_EXACT = [
    'Какое из предложений является вопросом?',
    'Какое из предложений является отрицанием?',
    'Какое из предложений является утверждением?',
    'Какой ответ правильный на вопрос "How many books?"',
    'Выберите правильный вариант предложения.',
]

def is_allowed_duplicate(prompt_text):
    """Проверяет, является ли prompt разрешенным дубликатом"""
    prompt_text = prompt_text.strip()
    
    if prompt_text in ALLOWED_DUPLICATE_EXACT:
        return True
    
    for pattern in ALLOWED_DUPLICATE_PREFIXES:
        if prompt_text.startswith(pattern):
            return True
    
    return False

# Собираем все вопросы из всех глав
all_questions = {}  # prompt -> list of (chapter_id, question_id)

# Находим все папки глав
chapter_dirs = [d for d in chapters_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

for chapter_dir in sorted(chapter_dirs):
    final_file = chapter_dir / '05-final.json'
    
    if not final_file.exists():
        continue
    
    # Извлекаем chapter_id из имени папки
    chapter_name = chapter_dir.name
    chapter_id = chapter_name.split('.', 1)[-1] if '.' in chapter_name else chapter_name
    
    try:
        with open(final_file, 'r', encoding='utf-8') as f:
            chapter = json.load(f)
        
        questions = chapter.get('question_bank', {}).get('questions', [])
        
        for q in questions:
            qid = q.get('id')
            qtype = q.get('type')
            prompt = q.get('prompt', '').strip()
            
            # Пропускаем reorder и разрешенные дубликаты
            if qtype == 'reorder' or not prompt or is_allowed_duplicate(prompt):
                continue
            
            # Сохраняем информацию о вопросе
            if prompt not in all_questions:
                all_questions[prompt] = []
            all_questions[prompt].append((chapter_id, qid))
    
    except Exception as e:
        print(f"Ошибка при чтении {final_file}: {e}", file=sys.stderr)
        continue

# Проверяем дубликаты
duplicates = {prompt: questions_list for prompt, questions_list in all_questions.items() if len(questions_list) > 1}

if duplicates:
    print("Найдены дубликаты вопросов между главами:")
    print("=" * 80)
    
    total_duplicates = 0
    for prompt, questions_list in sorted(duplicates.items()):
        total_duplicates += len(questions_list) - 1  # Минус один, так как один можно оставить
        
        # Группируем по главам
        chapters_with_duplicate = defaultdict(list)
        for chapter_id, qid in questions_list:
            chapters_with_duplicate[chapter_id].append(qid)
        
        print(f"\nДубликат prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        for chapter_id, qids in sorted(chapters_with_duplicate.items()):
            print(f"  Глава {chapter_id}: {', '.join(qids)}")
    
    print("\n" + "=" * 80)
    print(f"Всего найдено дубликатов: {len(duplicates)}")
    print(f"Всего вопросов-дубликатов (кроме первого в каждой группе): {total_duplicates}")
    print("\nРекомендация: удалите дубликаты, оставив по одному вопросу в каждой группе.")
    exit(1)
else:
    print("✓ Все вопросы уникальны по всему курсу (кроме разрешенных исключений)")
    exit(0)
PYTHON_SCRIPT

EXIT_CODE=$?
exit $EXIT_CODE
