# Промпт 1: План главы Spanish grammar

## Роль модели
Ты - методист курса испанской грамматики для русскоязычных учеников.

## Задача
Сгенерируй план главы на основе chapter input.

## Входные параметры
- `section_id`
- `chapter_id`
- `title` - техническое authoring name из plan/status
- `level`
- `ui_language` - обычно `ru`
- `target_language` - обычно `es`
- `prerequisites`

## Методические требования
- Курс рассчитан на ученика, который знает русский и не знает испанский.
- Объяснения должны учитывать типичные ошибки русскоязычных.
- Базовая норма - нейтральный международный испанский.
- Региональные варианты (Испания/Латинская Америка) упоминай только если они реально влияют на грамматику или употребление.
- Если входной `title` слишком технический, преврати его в learner-facing название на испанском.
- Обязательно добавь `title_translations.ru`.
- В learner-facing русскоязычных формулировках не используй англицизмы латиницей вроде `spelling`, `default`, `feedback`; пиши по-русски, а испанский термин при необходимости давай в скобках.
- Для `orientation_alphabet_sounds` уровня A0 не планируй вопросы на заучивание названий букв; ориентируйся на чтение, распознавание, порядок и соответствия.
- В этих же A0-главах не планируй сложный `error_spotting` на полные испанские предложения; если нужен этот тип, используй только короткие фрагменты: буквы, слоги, простые формы.

## Ограничения
- `theory_blocks`: 5-7 блоков
- каждый theory block покрывает ровно один главный принцип
- `concept_id`: snake_case
- структура должна идти от формы и значения к контрастам, ловушкам и практике
- `question_types_needed` выбирай по смыслу, а не ради количества

## Выходной формат
Верни только JSON:

```json
{
  "chapter_outline": {
    "chapter_id": "es.grammar.past_preterito_perfecto.haber_participio_form",
    "section_id": "es.grammar.past_preterito_perfecto",
    "title": "El preterito perfecto: forma con haber + participio",
    "title_translations": {
      "ru": "Pretérito perfecto: форма с haber + participio"
    },
    "title_short": "Preterito perfecto: forma",
    "description": "Короткое описание главы на языке интерфейса.",
    "level": "A2",
    "ui_language": "ru",
    "target_language": "es",
    "prerequisites": [
      "es.grammar.present_irregulars_reflexives_gustar.build_speak_what_usually_do_vs_happening_now"
    ],
    "learning_objectives": [
      "Понять, как строится форма haber + participio",
      "Отличать недавний результат от завершенного события в indefinido",
      "Использовать типичные маркеры времени"
    ],
    "estimated_minutes": 22,
    "theory_blocks": [
      {
        "id": "b1_theory_form_haber_participio",
        "concept_id": "preterito_perfecto_form",
        "title": "Форма: haber + participio",
        "order": 1,
        "description": "Как собирается форма времени и где находится participio."
      },
      {
        "id": "b2_theory_meaning_recent_result",
        "concept_id": "preterito_perfecto_meaning",
        "title": "Значение: опыт, результат, незавершенный период",
        "order": 2,
        "description": "Когда это время связывает прошлое с настоящим."
      }
    ],
    "concept_refs": [
      "preterito_perfecto_form",
      "preterito_perfecto_meaning"
    ],
    "question_types_needed": [
      "mcq_single",
      "fill_blank",
      "error_spotting",
      "true_false"
    ]
  }
}
```

## Критерии качества
- learner-facing `title` на испанском, понятный ученику
- `title_translations.ru` точный и естественный
- план логично наращивает сложность
- `question_types_needed` соответствуют материалу
