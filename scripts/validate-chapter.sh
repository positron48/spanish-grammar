#!/bin/bash

# Скрипт для валидации главы
# Использование: ./scripts/validate-chapter.sh <chapter_id>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHAPTER_ID="${1:-}"

# Подключаем утилиты для работы с именами папок
source "$SCRIPT_DIR/chapter-utils.sh"

if [ -z "$CHAPTER_ID" ]; then
    echo "Ошибка: укажите chapter_id"
    echo "Использование: $0 <chapter_id>"
    exit 1
fi

# Получаем путь к папке главы (может быть с префиксом или без)
CHAPTER_DIR=$(get_chapter_dir "$CHAPTER_ID" "$PROJECT_ROOT/chapters")
if [ $? -ne 0 ]; then
    echo "Ошибка: папка главы не найдена: $CHAPTER_ID"
    exit 1
fi

# Получаем имя папки главы (с префиксом, если есть)
CHAPTER_FOLDER_NAME=$(basename "$CHAPTER_DIR")

SCHEMA_FILE="$PROJECT_ROOT/02-chapter-schema.json"
FINAL_FILE="$CHAPTER_DIR/05-final.json"
VALIDATION_OUTPUT="$CHAPTER_DIR/05-validation.json"

if [ ! -f "$FINAL_FILE" ]; then
    echo "Ошибка: не найден $FINAL_FILE"
    echo "Сначала соберите финальный JSON: ./scripts/assemble-chapter.sh $CHAPTER_ID"
    exit 1
fi

# Запускаем Python скрипт валидации
python3 << PYTHON_SCRIPT
import json
import re
import sys

# Читаем схему и главу
try:
    with open('$SCHEMA_FILE', 'r', encoding='utf-8') as f:
        schema = json.load(f)
except Exception as e:
    print(f"Ошибка чтения схемы: {e}", file=sys.stderr)
    sys.exit(1)

try:
    with open('$FINAL_FILE', 'r', encoding='utf-8') as f:
        chapter = json.load(f)
except Exception as e:
    print(f"Ошибка чтения главы: {e}", file=sys.stderr)
    sys.exit(1)

issues = []
errors = 0
warnings = 0
suggestions = 0

# 1. Структурная валидность
# Проверка level
if chapter.get('level') not in ['A0', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'mixed']:
    issues.append({
        'severity': 'error',
        'category': 'structural',
        'message': f"Level '{chapter.get('level')}' не соответствует схеме. Допустимые значения: A0, A1, A2, B1, B2, C1, C2, mixed",
        'location': 'level',
        'suggested_fix': 'Изменить level на одно из допустимых значений'
    })
    errors += 1

# Проверка title на отсутствие markdown
def contains_markdown(text):
    """Проверяет, содержит ли текст markdown синтаксис"""
    if not text:
        return False
    
    # Паттерны markdown для проверки
    # Используем \x60 (hex escape) для обратных кавычек, чтобы избежать проблем с bash heredoc
    backtick = '\x60'
    markdown_patterns = [
        r'\*\*[^*]+\*\*',      # **bold** (минимум один символ между **)
        r'__[^_]+__',          # __bold__ (минимум один символ между __)
        r'(?<!\*)\*[^*\s][^*]*[^*\s]\*(?!\*)',  # *italic* (не в начале/конце, не окружен другими *)
        r'(?<!_)_[^_\s][^_]*[^_\s]_(?!_)',      # _italic_ (не в начале/конце, не окружен другими _)
        backtick + r'[^' + backtick + r'\n]+' + backtick,  # inline code (обратные кавычки)
        r'\[[^\]]+\]\([^\)]+\)',  # [link](url)
        r'^#{1,6}\s',          # heading (в начале строки)
        r'^>\s',               # quote (в начале строки)
        r'^[-*+]\s',           # list (в начале строки)
        r'^---+$',             # horizontal rule (только дефисы)
        r'^\*\*\*+$',          # horizontal rule (только звездочки)
        backtick + backtick + backtick,  # code block (три обратные кавычки)
    ]
    
    for pattern in markdown_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    
    return False

title = chapter.get('title', '')
if title and contains_markdown(title):
    issues.append({
        'severity': 'error',
        'category': 'structural',
        'message': f"Название главы содержит markdown синтаксис: '{title}'. Название должно быть обычным текстом без markdown разметки.",
        'location': 'title',
        'suggested_fix': 'Удалить markdown разметку из названия главы (убрать **, *, обратные кавычки, #, >, и т.д.)'
    })
    errors += 1

# Собираем все theory_block_id
theory_blocks = {}
blocks = chapter.get('blocks') or []
for block in blocks:
    if block.get('type') == 'theory':
        theory_blocks[block['id']] = block

# Собираем все question_ids
question_bank = chapter.get('question_bank', {})
questions = question_bank.get('questions') or []
question_ids = {q['id']: q for q in questions}

# 2. Содержательная валидность
# Проверка theory_block_id в вопросах
for q in questions:
    if q['theory_block_id'] not in theory_blocks:
        issues.append({
            'severity': 'error',
            'category': 'structural',
            'message': f"Question {q['id']} references non-existent theory_block_id '{q['theory_block_id']}'",
            'location': f"question_bank.questions[{questions.index(q)}]",
            'suggested_fix': 'Изменить theory_block_id на существующий ID блока теории'
        })
        errors += 1

# Проверка question_ids в quiz_inline
for block in blocks:
    if block['type'] == 'quiz_inline':
        for qid in block['quiz_inline']['question_ids']:
            if qid not in question_ids:
                issues.append({
                    'severity': 'error',
                    'category': 'structural',
                    'message': f"Quiz inline block {block['id']} references non-existent question_id '{qid}'",
                    'location': f"blocks[{blocks.index(block)}].quiz_inline.question_ids",
                    'suggested_fix': 'Изменить question_id на существующий ID вопроса'
                })
                errors += 1

# Проверка question_ids в chapter_test
chapter_test = chapter.get('chapter_test', {})
pool_question_ids = chapter_test.get('pool_question_ids') or []
for qid in pool_question_ids:
    if qid not in question_ids:
        issues.append({
            'severity': 'error',
            'category': 'structural',
            'message': f"Chapter test references non-existent question_id '{qid}'",
            'location': 'chapter_test.pool_question_ids',
            'suggested_fix': 'Удалить несуществующий question_id из pool_question_ids'
        })
        errors += 1

# Проверка соответствия correct_answer типу вопроса
for q in questions:
    qid = q['id']
    qtype = q['type']
    correct_answer = q.get('correct_answer')
    
    if qtype == 'mcq_single':
        if 'choices' not in q:
            issues.append({
                'severity': 'error',
                'category': 'structural',
                'message': f"Question {qid}: mcq_single requires 'choices' field",
                'location': f"question_bank.questions[{questions.index(q)}]",
                'suggested_fix': 'Add choices array to question'
            })
            errors += 1
        elif correct_answer not in [c['id'] for c in q['choices']]:
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: correct_answer '{correct_answer}' не найден в choices. Для mcq_single correct_answer должен быть ID одного из choices.",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].correct_answer",
                'suggested_fix': 'Изменить correct_answer на ID одного из choices (a, b, c и т.д.)'
            })
            errors += 1
    
    elif qtype == 'mcq_multi':
        if 'choices' not in q:
            issues.append({
                'severity': 'error',
                'category': 'structural',
                'message': f"Question {qid}: mcq_multi requires 'choices' field",
                'location': f"question_bank.questions[{questions.index(q)}]",
                'suggested_fix': 'Add choices array to question'
            })
            errors += 1
        elif not isinstance(correct_answer, list):
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: correct_answer должен быть массивом для mcq_multi",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].correct_answer",
                'suggested_fix': 'Изменить correct_answer на массив ID из choices'
            })
            errors += 1
        elif 'choices' in q:
            choice_ids = [c['id'] for c in q['choices']]
            if not all(ans in choice_ids for ans in correct_answer):
                issues.append({
                    'severity': 'error',
                    'category': 'content',
                    'message': f"Question {qid}: некоторые ID в correct_answer не найдены в choices",
                    'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].correct_answer",
                    'suggested_fix': 'Исправить correct_answer на массив существующих ID из choices'
                })
                errors += 1

    elif qtype == 'error_spotting':
        if 'choices' not in q:
            issues.append({
                'severity': 'error',
                'category': 'structural',
                'message': f"Question {qid}: error_spotting requires 'choices' field",
                'location': f"question_bank.questions[{questions.index(q)}]",
                'suggested_fix': 'Add choices array to question'
            })
            errors += 1
        else:
            choices = q.get('choices') or []
            if len(choices) < 3:
                issues.append({
                    'severity': 'error',
                    'category': 'content',
                    'message': f"Question {qid}: error_spotting должен иметь минимум 3 варианта ответа, найдено {len(choices)}",
                    'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].choices",
                    'suggested_fix': 'Добавить недостающие варианты в choices (минимум 3)'
                })
                errors += 1
    
    elif qtype == 'true_false':
        if correct_answer not in ['true', 'false']:
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: correct_answer должен быть 'true' или 'false' для true_false",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].correct_answer",
                'suggested_fix': "Изменить correct_answer на 'true' или 'false'"
            })
            errors += 1
        if 'choices' in q:
            issues.append({
                'severity': 'warning',
                'category': 'content',
                'message': f"Question {qid}: true_false не должен содержать choices",
                'location': f"question_bank.questions[{questions.index(q)}]",
                'suggested_fix': 'Удалить поле choices для true_false вопроса'
            })
            warnings += 1
    
    elif qtype == 'fill_blank':
        if not isinstance(correct_answer, str):
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: correct_answer должен быть строкой для fill_blank",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].correct_answer",
                'suggested_fix': 'Изменить correct_answer на строку'
            })
            errors += 1
        else:
            # Проверка fill_blank: correct_answer должен быть одним словом (допускается апостроф)
            correct_normalized = correct_answer.strip()
            # Проверяем, что это одно слово (могут быть буквы, цифры, апострофы, дефисы в пределах слова)
            if re.search(r'\s', correct_normalized):
                issues.append({
                    'severity': 'error',
                    'category': 'content',
                    'message': f"Question {qid}: correct_answer для fill_blank должен быть одним словом, найдено: '{correct_answer}'",
                    'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].correct_answer",
                    'suggested_fix': f"Изменить correct_answer на одно слово. Если нужны несколько пропусков, создайте несколько вопросов или используйте другой тип вопроса."
                })
                errors += 1
        
        # Проверка fill_blank: обязательные скобки в конце prompt со словами для подстановки
        prompt = q.get('prompt', '')
        bracket_match = re.search(r'\(([^)]+)\)\s*$', prompt)
        
        if not bracket_match:
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: fill_blank должен содержать скобки в конце prompt с базовой формой слова/слов для подстановки",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].prompt",
                'suggested_fix': f"Добавить скобки в конце промпта. Например: \"...\" ({'базовая форма'})"
            })
            errors += 1
        else:
            bracket_content = bracket_match.group(1).strip()
            # Разделяем на варианты (через / или запятую)
            variants = re.split(r'\s*[/,]\s*', bracket_content)
            variants = [v.strip() for v in variants]
            
            # Проверяем, что в скобках не та же форма, что в correct_answer
            # Сравниваем с учетом регистра для правильных ответов с заглавной буквы
            correct_lower = correct_answer.lower().strip()
            correct_normalized = correct_answer.strip()
            
            # Проверяем каждую часть correct_answer (если разделено через /)
            correct_parts = re.split(r'\s*/\s*', correct_normalized)
            correct_parts_normalized = [p.strip() for p in correct_parts]
            
            # Проверяем совпадение
            bracket_variants_lower = [v.lower().strip() for v in variants]
            bracket_variants_normalized = [v.strip() for v in variants]
            
            has_match = False
            for bracket_var in bracket_variants_normalized:
                bracket_var_lower = bracket_var.lower()
                # Проверяем точное совпадение или совпадение без учета регистра
                if bracket_var_lower == correct_lower or bracket_var in correct_parts_normalized or bracket_var_lower in [cp.lower() for cp in correct_parts_normalized]:
                    has_match = True
                    break
            
            if has_match:
                issues.append({
                    'severity': 'error',
                    'category': 'content',
                    'message': f"Question {qid}: в скобках указана та же форма '{bracket_content}', что и в correct_answer '{correct_answer}'. В скобках должна быть базовая форма или другая форма, но не та же самая.",
                    'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].prompt",
                    'suggested_fix': f"Изменить скобки на базовую форму. Например, если correct_answer '{correct_answer}', то в скобках указать базовую форму глагола или другую подсказку."
                })
                errors += 1
    
    elif qtype == 'reorder':
        if not isinstance(correct_answer, str):
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: correct_answer должен быть строкой (полное предложение) для reorder",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].correct_answer",
                'suggested_fix': 'Изменить correct_answer на полное предложение'
            })
            errors += 1
        
        # Проверка reorder: prompt должен быть точно "Расставьте слова в правильном порядке:"
        prompt = q.get('prompt', '').strip()
        expected_prompt = "Расставьте слова в правильном порядке:"
        if prompt != expected_prompt:
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: reorder должен иметь prompt точно '{expected_prompt}'. Найдено: '{prompt}'. Слова должны браться из correct_answer, а не перечисляться в prompt.",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].prompt",
                'suggested_fix': f"Изменить prompt на '{expected_prompt}'. Убрать перечисление слов из prompt."
            })
            errors += 1

# Проверка уникальности feedback в choices
for q in questions:
    qid = q['id']
    qtype = q['type']
    
    # Проверяем только вопросы с choices
    if qtype in ['mcq_single', 'mcq_multi'] and 'choices' in q:
        feedback_choices = {}  # Для отслеживания, какие choices имеют одинаковый feedback
        
        for choice in q['choices']:
            if 'feedback' in choice and choice['feedback']:
                feedback_text = choice['feedback'].strip()
                if feedback_text:
                    if feedback_text not in feedback_choices:
                        feedback_choices[feedback_text] = []
                    feedback_choices[feedback_text].append(choice.get('id', 'unknown'))
        
        # Проверяем на дубликаты (если один feedback используется в нескольких choices)
        duplicates = {fb: choice_ids for fb, choice_ids in feedback_choices.items() if len(choice_ids) > 1}
        
        if duplicates:
            duplicate_info = []
            for dup_feedback, choice_ids in duplicates.items():
                duplicate_info.append(f"'{dup_feedback}' (используется в choices: {', '.join(choice_ids)})")
            
            issues.append({
                'severity': 'error',
                'category': 'content',
                'message': f"Question {qid}: найдены одинаковые feedback в choices. Дубликаты: {', '.join(duplicate_info)}",
                'location': f"question_bank.questions[{chapter['question_bank']['questions'].index(q)}].choices",
                'suggested_fix': 'Изменить feedback для каждого choice, чтобы они были уникальными'
            })
            errors += 1

# Проверка уникальности текста вопросов (prompt), кроме типа reorder
# Список общих вопросов, которые могут повторяться с разными вариантами ответов
# Паттерны, которые проверяются как начало строки (могут иметь продолжение)
allowed_duplicate_prefixes = [
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

# Паттерны, которые проверяются как точное совпадение (полные вопросы)
allowed_duplicate_exact = [
    'Какое из предложений является вопросом?',
    'Какое из предложений является отрицанием?',
    'Какое из предложений является утверждением?',
    'Какой ответ правильный на вопрос "How many books?"',
    'Выберите правильный вариант предложения.',
]

prompt_questions = {}  # Для отслеживания, какие вопросы имеют одинаковый prompt
for q in questions:
    qid = q['id']
    qtype = q['type']
    
    # Пропускаем вопросы типа reorder
    if qtype == 'reorder':
        continue
    
    prompt_text = q.get('prompt', '').strip()
    if prompt_text:
        # Пропускаем общие вопросы, которые могут повторяться с разными ответами
        is_allowed_duplicate = False
        
        # Проверяем точное совпадение для полных вопросов
        if prompt_text in allowed_duplicate_exact:
            is_allowed_duplicate = True
        else:
            # Проверяем начало строки для паттернов-префиксов
            for pattern in allowed_duplicate_prefixes:
                if prompt_text.startswith(pattern):
                    is_allowed_duplicate = True
                    break
        
        if not is_allowed_duplicate:
            if prompt_text not in prompt_questions:
                prompt_questions[prompt_text] = []
            prompt_questions[prompt_text].append(qid)

# Проверяем на дубликаты (если один prompt используется в нескольких вопросах)
duplicates = {prompt: question_ids for prompt, question_ids in prompt_questions.items() if len(question_ids) > 1}

if duplicates:
    for dup_prompt, question_ids in duplicates.items():
        issues.append({
            'severity': 'error',
            'category': 'content',
            'message': f"Найдены вопросы с одинаковым текстом (prompt): '{dup_prompt}'. Дубликаты в вопросах: {', '.join(question_ids)}",
            'location': 'question_bank.questions',
            'suggested_fix': f"Изменить prompt для одного или нескольких вопросов ({', '.join(question_ids)}), чтобы они были уникальными"
        })
        errors += 1

# Проверка уникальности пары prompt + correct_answer (в пределах главы)
def normalize_correct_answer(question):
    qtype = question.get('type')
    correct = question.get('correct_answer')
    choices = question.get('choices') or []

    # Для вопросов с choices используем текст вариантов, а не ID
    if qtype in ['mcq_single', 'mcq_multi', 'error_spotting'] and choices:
        choice_map = {c.get('id'): c.get('text', '').strip() for c in choices}
        if qtype == 'mcq_multi' and isinstance(correct, list):
            texts = [choice_map.get(cid, str(cid).strip()) for cid in correct]
            # Сортируем, чтобы одинаковые наборы считались одинаковыми
            return sorted([t for t in texts if t != ''])
        return choice_map.get(correct, str(correct).strip())
        return str(correct).strip()

    # Для остальных типов используем значение correct_answer напрямую
    if isinstance(correct, (dict, list)):
        return json.dumps(correct, ensure_ascii=False, sort_keys=True)
    if correct is None:
        return ''
    return str(correct).strip()

prompt_answer_pairs = {}
long_answer_map = {}
for q in questions:
    prompt_text = q.get('prompt', '').strip()
    if not prompt_text:
        continue
    normalized_answer = normalize_correct_answer(q)
    if normalized_answer == '':
        continue
    if isinstance(normalized_answer, list):
        normalized_answer_str = ' | '.join(normalized_answer)
    else:
        normalized_answer_str = str(normalized_answer)
    pair_key = (prompt_text, json.dumps(normalized_answer_str, ensure_ascii=False))
    if pair_key not in prompt_answer_pairs:
        prompt_answer_pairs[pair_key] = []
    prompt_answer_pairs[pair_key].append(q['id'])

    # Проверка уникальности правильных ответов длиной > 10 символов
    if len(normalized_answer_str) > 10:
        if normalized_answer_str not in long_answer_map:
            long_answer_map[normalized_answer_str] = []
        long_answer_map[normalized_answer_str].append(q['id'])

pair_duplicates = {key: qids for key, qids in prompt_answer_pairs.items() if len(qids) > 1}

if pair_duplicates:
    for (dup_prompt, dup_answer), qids in pair_duplicates.items():
        issues.append({
            'severity': 'error',
            'category': 'content',
            'message': f"Найдены вопросы с одинаковой парой prompt+correct_answer: '{dup_prompt}' / '{dup_answer}'. Дубликаты: {', '.join(qids)}",
            'location': 'question_bank.questions',
            'suggested_fix': f"Изменить prompt или correct_answer для одного из вопросов ({', '.join(qids)}), чтобы пары были уникальными"
        })
        errors += 1

long_answer_duplicates = {answer: qids for answer, qids in long_answer_map.items() if len(qids) > 1}
if long_answer_duplicates:
    for answer_text, qids in long_answer_duplicates.items():
        issues.append({
            'severity': 'error',
            'category': 'content',
            'message': f"Найдены одинаковые правильные ответы длиной > 10 символов: '{answer_text}'. Дубликаты: {', '.join(qids)}",
            'location': 'question_bank.questions',
            'suggested_fix': f"Изменить correct_answer для одного из вопросов ({', '.join(qids)}), чтобы все длинные ответы были уникальными"
        })
        errors += 1

# 3. Методическая валидность
# Проверка наличия content_md в theory_blocks (обязательное поле)
for block in blocks:
    if block['type'] == 'theory':
        block_id = block['id']
        if not block['theory'].get('content_md') or len(block['theory'].get('content_md', '').strip()) == 0:
            issues.append({
                'severity': 'error',
                'category': 'structural',
                'message': f"Theory block {block_id}: отсутствует обязательное поле content_md",
                'location': f'blocks[].theory.content_md (theory_block_id: {block_id})',
                'suggested_fix': 'Добавить content_md с теоретическим объяснением'
            })
            errors += 1

# Количество theory_blocks
num_theory_blocks = len([b for b in blocks if b.get('type') == 'theory'])
if num_theory_blocks > 9:
    issues.append({
        'severity': 'warning',
        'category': 'methodological',
        'message': f"Найдено {num_theory_blocks} theory_blocks, максимум 9 разрешено",
        'location': 'blocks[].type',
        'suggested_fix': 'Объединить или удалить лишние theory_blocks'
    })
    warnings += 1

# Проверка наличия explanation у всех вопросов
for q in questions:
    if not q.get('explanation') or len(q.get('explanation', '').strip()) == 0:
        issues.append({
            'severity': 'error',
            'category': 'methodological',
            'message': f"Question {q['id']} не содержит explanation",
            'location': f"question_bank.questions[{questions.index(q)}]",
            'suggested_fix': 'Добавить explanation к вопросу'
        })
        errors += 1

# Проверка покрытия theory_blocks вопросами
theory_blocks_covered = set()
for q in questions:
    if q.get('theory_block_id') in theory_blocks:
        theory_blocks_covered.add(q['theory_block_id'])

for block_id in theory_blocks:
    if block_id not in theory_blocks_covered:
        issues.append({
            'severity': 'warning',
            'category': 'content',
            'message': f"Theory block {block_id} не покрыт вопросами",
            'location': 'question_bank.questions',
            'suggested_fix': 'Добавить вопросы для этого theory_block'
        })
        warnings += 1

# Подсчет вопросов по блокам
questions_per_block = {}
for q in questions:
    block_id = q.get('theory_block_id')
    if block_id:
        questions_per_block[block_id] = questions_per_block.get(block_id, 0) + 1

# Проверка минимального количества вопросов на блок (минимум 4)
for block_id in theory_blocks:
    question_count = questions_per_block.get(block_id, 0)
    if question_count < 4:
        issues.append({
            'severity': 'warning',
            'category': 'methodological',
            'message': f"Theory block {block_id} имеет только {question_count} вопрос(ов), минимум 4 требуется",
            'location': 'question_bank.questions',
            'suggested_fix': f'Добавить вопросы для theory_block {block_id}. Сейчас: {question_count}, нужно минимум 4'
        })
        warnings += 1

# Проверка баланса true_false вопросов (50±30% должны быть true)
true_false_questions = [q for q in questions if q.get('type') == 'true_false']
if len(true_false_questions) > 0:
    true_count = sum(1 for q in true_false_questions if q.get('correct_answer') == 'true')
    false_count = sum(1 for q in true_false_questions if q.get('correct_answer') == 'false')
    total_tf = len(true_false_questions)
    true_percentage = (true_count / total_tf) * 100 if total_tf > 0 else 0
    
    # Допустимый диапазон: 20-80% (50±30%)
    # Игнорируем правило, если таких вопросов меньше 3
    min_percentage = 20
    max_percentage = 80
    
    if total_tf >= 3 and (true_percentage < min_percentage or true_percentage > max_percentage):
        issues.append({
            'severity': 'warning',
            'category': 'methodological',
            'message': f"Несбалансированные true_false вопросы: {true_count} true ({true_percentage:.1f}%) и {false_count} false ({100-true_percentage:.1f}%). Должно быть 50±30% (20-80%) вопросов с correct_answer 'true'.",
            'location': 'question_bank.questions (true_false)',
            'suggested_fix': f"Изменить correct_answer некоторых true_false вопросов. Сейчас true: {true_count}, false: {false_count}. Нужно примерно равное количество."
        })
        warnings += 1

# Формируем результат
result = {
    'validation_result': {
        'is_valid': errors == 0,
        'schema_valid': errors == 0,
        'issues': issues,
        'summary': {
            'total_issues': len(issues),
            'errors': errors,
            'warnings': warnings,
            'suggestions': suggestions
        },
        'coverage': {
            'theory_blocks_covered': len(theory_blocks_covered),
            'total_theory_blocks': len(theory_blocks),
            'questions_per_block': questions_per_block
        }
    }
}

# Сохраняем результат
with open('$VALIDATION_OUTPUT', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# Цвета для вывода
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Выводим краткую информацию с цветами
chapter_id = '$CHAPTER_ID'
chapter_folder = '$CHAPTER_FOLDER_NAME'
# Формируем отображаемое имя: показываем папку (с номером), если она отличается от chapter_id
# Если папка совпадает с chapter_id, показываем только chapter_id
display_name = chapter_folder if chapter_folder != chapter_id else chapter_id

if errors == 0 and warnings == 0:
    print(f"{Colors.GREEN}✓{Colors.RESET} {display_name}: валидно")
    sys.exit(0)
else:
    # Выводим ошибки и предупреждения кратко
    print(f"{display_name}:", end=' ')
    if errors > 0:
        print(f"{Colors.RED}✗ {errors} ошибок{Colors.RESET}")
        for issue in issues:
            if issue['severity'] == 'error':
                print(f"  {Colors.RED}✗{Colors.RESET} {issue['message']}")
    
    if warnings > 0:
        if errors == 0:
            print(f"{Colors.YELLOW}⚠ {warnings} предупреждений{Colors.RESET}")
        else:
            print(f"\n{Colors.YELLOW}⚠ {warnings} предупреждений{Colors.RESET}")
        for issue in issues:
            if issue['severity'] == 'warning':
                print(f"  {Colors.YELLOW}⚠{Colors.RESET} {issue['message']}")
    
    sys.exit(1 if errors > 0 else 0)
PYTHON_SCRIPT

EXIT_CODE=$?
exit $EXIT_CODE
