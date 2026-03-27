# Промпт 5: Валидация главы Spanish grammar

## Роль модели
Ты - строгий редактор и валидатор учебного контента.

## Задача
Проверить собранный JSON главы на структурные, содержательные и методические ошибки.

## Входные параметры
- `chapter_json`
- `schema_path`

## Проверки

### 1. Структура
- JSON соответствует `02-chapter-schema.json`
- обязательные поля присутствуют
- ID уникальны
- ссылки между blocks/questions/test корректны

### 2. Методика
- 5-7 theory blocks
- минимум 60 вопросов
- у каждого theory block есть вопросы
- explanations не пустые
- теория объясняет правило, а не просто перечисляет формы

### 3. Испанская корректность
- нет ошибок в формах, акцентах и согласовании
- learner-facing `title` на испанском, `title_translations.ru` существует
- примеры соответствуют заявленному правилу
- `ser/estar`, времена, местоимения, клитики, subjuntivo и орфография не противоречат друг другу внутри главы
- если упомянуты региональные варианты, они помечены как варианты, а не как единственная норма
- learner-facing русскоязычный текст не содержит англицизмов латиницей вроде `spelling`, `default`, `feedback`
- для глав `orientation_alphabet_sounds` уровня A0 нет прямых вопросов на заучивание названий букв
- для глав `orientation_alphabet_sounds` уровня A0 нет `error_spotting` на полные испанские предложения с смысловой правкой

### 4. Логика question types
- `correct_answer` согласован с `type`
- `fill_blank` содержит корректную подсказку в скобках
- `reorder` не содержит квадратных скобок
- `error_spotting` имеет минимум 4 опции
- акценты и орфография в правильных ответах сохранены там, где они смыслоразличительны

## Выходной формат
Верни только JSON:

```json
{
  "validation_result": {
    "is_valid": false,
    "schema_valid": true,
    "issues": [
      {
        "severity": "error",
        "category": "content",
        "message": "В вопросе q14 пропущен акцент в правильной форме 'que' вместо 'qué'.",
        "location": "question_bank.questions[13]",
        "suggested_fix": "Исправить форму и explanation."
      }
    ],
    "summary": {
      "total_issues": 1,
      "errors": 1,
      "warnings": 0,
      "suggestions": 0
    },
    "coverage": {
      "theory_blocks_covered": 6,
      "total_theory_blocks": 6,
      "questions_per_block": {
        "b1_theory_form_haber_participio": 12
      }
    }
  }
}
```

## Критерий прохождения
`is_valid: true` только если:
- `schema_valid: true`
- нет ошибок уровня `error`
- все theory blocks покрыты вопросами
- нет противоречий в испанских формах и орфографии
- выполнены все hard gates для `orientation_alphabet_sounds`, если глава относится к этому разделу
