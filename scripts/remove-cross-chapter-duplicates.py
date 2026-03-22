#!/usr/bin/env python3
"""
Скрипт для удаления дубликатов вопросов между главами.
Удаляет вопросы с одинаковым prompt (кроме типа reorder и разрешенных паттернов).
Оставляет первый вопрос в каждой группе дубликатов.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Паттерны, которые могут повторяться
ALLOWED_DUPLICATE_PREFIXES = [
    'Выберите правильный вариант:',
    'Выберите правильный императив:',
    'Выберите правильное отрицательное предложение:',
    'Выберите правильное предложение:',
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

def remove_question_from_list(questions, qid_to_remove):
    """Удаляет вопрос из списка"""
    return [q for q in questions if q['id'] != qid_to_remove]

def remove_question_from_quiz_inline(blocks, qid_to_remove):
    """Удаляет question_id из всех quiz_inline блоков"""
    for block in blocks:
        if block.get('type') == 'quiz_inline' and 'quiz_inline' in block:
            if 'question_ids' in block['quiz_inline']:
                block['quiz_inline']['question_ids'] = [
                    qid for qid in block['quiz_inline']['question_ids'] 
                    if qid != qid_to_remove
                ]

def remove_question_from_chapter_test(chapter_test, qid_to_remove):
    """Удаляет question_id из chapter_test.pool_question_ids"""
    if 'pool_question_ids' in chapter_test:
        chapter_test['pool_question_ids'] = [
            qid for qid in chapter_test['pool_question_ids'] 
            if qid != qid_to_remove
        ]

def main():
    project_root = Path(__file__).parent.parent
    chapters_dir = project_root / 'chapters'
    
    # Собираем все вопросы из всех глав
    all_questions = {}  # prompt -> list of (chapter_dir, chapter_id, question_id, question_obj)
    
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
                all_questions[prompt].append((chapter_dir, chapter_id, qid, q))
        
        except Exception as e:
            print(f"Ошибка при чтении {final_file}: {e}", file=sys.stderr)
            continue
    
    # Находим дубликаты
    duplicates = {prompt: questions_list for prompt, questions_list in all_questions.items() if len(questions_list) > 1}
    
    if not duplicates:
        print("✓ Дубликатов не найдено")
        return
    
    print(f"Найдено {len(duplicates)} групп дубликатов")
    print("Удаление дубликатов (оставляем первый вопрос в каждой группе)...\n")
    
    total_removed = 0
    
    # Обрабатываем каждую группу дубликатов
    for prompt, questions_list in sorted(duplicates.items()):
        # Оставляем первый, удаляем остальные
        first_chapter_dir, first_chapter_id, first_qid, first_q = questions_list[0]
        
        print(f"Дубликат: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"  Оставляем: {first_chapter_id}:{first_qid}")
        
        # Удаляем остальные вопросы
        for chapter_dir, chapter_id, qid_to_remove, q in questions_list[1:]:
            print(f"  Удаляем: {chapter_id}:{qid_to_remove}")
            
            # Читаем главу
            final_file = chapter_dir / '05-final.json'
            with open(final_file, 'r', encoding='utf-8') as f:
                chapter = json.load(f)
            
            # Удаляем из question_bank
            chapter['question_bank']['questions'] = remove_question_from_list(
                chapter['question_bank']['questions'], qid_to_remove
            )
            
            # Удаляем из quiz_inline блоков
            remove_question_from_quiz_inline(chapter['blocks'], qid_to_remove)
            
            # Удаляем из chapter_test
            remove_question_from_chapter_test(chapter['chapter_test'], qid_to_remove)
            
            # Сохраняем
            with open(final_file, 'w', encoding='utf-8') as f:
                json.dump(chapter, f, ensure_ascii=False, indent=2)
            
            # Обновляем 03-questions.json если существует
            questions_file = chapter_dir / '03-questions.json'
            if questions_file.exists():
                with open(questions_file, 'r', encoding='utf-8') as f:
                    questions_data = json.load(f)
                
                if 'questions' in questions_data:
                    questions_data['questions'] = remove_question_from_list(
                        questions_data['questions'], qid_to_remove
                    )
                    
                    with open(questions_file, 'w', encoding='utf-8') as f:
                        json.dump(questions_data, f, ensure_ascii=False, indent=2)
            
            total_removed += 1
        
        print()
    
    print(f"✓ Удалено вопросов: {total_removed}")

if __name__ == '__main__':
    main()
