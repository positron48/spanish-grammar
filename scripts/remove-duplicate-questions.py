#!/usr/bin/env python3
"""
Скрипт для удаления дубликатов вопросов из глав.
Удаляет вопросы с одинаковым prompt (кроме типа reorder и разрешенных паттернов).
"""

import json
import sys
import os
from pathlib import Path

# Паттерны, которые могут повторяться
ALLOWED_DUPLICATE_PREFIXES = [
    'Выберите правильный вариант:',
    'Выберите правильный императив:',
    'Выберите правильное отрицательное предложение:',
    'Выберите правильное предложение:',
    'Выберите правильный вариант предложения:',
    'Выберите правильный вариант вопроса:',
    'Выберите правильный вариант отрицания:',
    'Выберите правильный вопрос о текущем действии:',
    'Выберите правильный вопрос о привычках:',
    'Выберите правильный вариант для выражения существования книги на столе:',
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

def find_duplicates(questions):
    """Находит дубликаты вопросов по prompt"""
    prompt_map = {}
    
    for q in questions:
        qid = q['id']
        qtype = q['type']
        prompt = q.get('prompt', '').strip()
        
        # Пропускаем reorder и разрешенные дубликаты
        if qtype == 'reorder' or not prompt or is_allowed_duplicate(prompt):
            continue
        
        if prompt not in prompt_map:
            prompt_map[prompt] = []
        prompt_map[prompt].append(qid)
    
    # Возвращаем только дубликаты (более одного вопроса)
    duplicates = {prompt: qids for prompt, qids in prompt_map.items() if len(qids) > 1}
    return duplicates

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

def process_chapter(chapter_dir):
    """Обрабатывает одну главу"""
    chapter_dir = Path(chapter_dir)
    final_file = chapter_dir / '05-final.json'
    questions_file = chapter_dir / '03-questions.json'
    
    if not final_file.exists():
        print(f"Пропуск: {chapter_dir.name} - нет 05-final.json")
        return False
    
    # Читаем final.json
    with open(final_file, 'r', encoding='utf-8') as f:
        chapter = json.load(f)
    
    questions = chapter['question_bank']['questions']
    duplicates = find_duplicates(questions)
    
    if not duplicates:
        return False
    
    print(f"\n{chapter_dir.name}:")
    removed_count = 0
    
    # Удаляем дубликаты (оставляем первый, удаляем остальные)
    for prompt, qids in duplicates.items():
        print(f"  Дубликаты: {', '.join(qids)}")
        # Оставляем первый, удаляем остальные
        for qid_to_remove in qids[1:]:
            print(f"    Удаляем: {qid_to_remove}")
            
            # Удаляем из question_bank
            questions = remove_question_from_list(questions, qid_to_remove)
            
            # Удаляем из quiz_inline блоков
            remove_question_from_quiz_inline(chapter['blocks'], qid_to_remove)
            
            # Удаляем из chapter_test
            remove_question_from_chapter_test(chapter['chapter_test'], qid_to_remove)
            
            removed_count += 1
    
    # Обновляем chapter
    chapter['question_bank']['questions'] = questions
    
    # Сохраняем final.json
    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump(chapter, f, ensure_ascii=False, indent=2)
    
    # Обновляем 03-questions.json если существует
    if questions_file.exists():
        with open(questions_file, 'r', encoding='utf-8') as f:
            questions_data = json.load(f)
        
        if 'questions' in questions_data:
            # Удаляем те же вопросы
            for prompt, qids in duplicates.items():
                for qid_to_remove in qids[1:]:
                    questions_data['questions'] = remove_question_from_list(
                        questions_data['questions'], qid_to_remove
                    )
            
            with open(questions_file, 'w', encoding='utf-8') as f:
                json.dump(questions_data, f, ensure_ascii=False, indent=2)
    
    print(f"  Удалено вопросов: {removed_count}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 remove-duplicate-questions.py <chapter_dir> [chapter_dir2 ...]")
        print("Или: python3 remove-duplicate-questions.py --all")
        sys.exit(1)
    
    if sys.argv[1] == '--all':
        # Обрабатываем все главы
        chapters_dir = Path(__file__).parent.parent / 'chapters'
        chapter_dirs = [d for d in chapters_dir.iterdir() if d.is_dir()]
        processed = 0
        for chapter_dir in sorted(chapter_dirs):
            if process_chapter(chapter_dir):
                processed += 1
        print(f"\nОбработано глав: {processed}")
    else:
        # Обрабатываем указанные главы
        for chapter_path in sys.argv[1:]:
            process_chapter(chapter_path)

if __name__ == '__main__':
    main()
