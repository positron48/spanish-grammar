#!/usr/bin/env python3
"""Generate speaking seed tasks for Spanish grammar course."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS_DIR = ROOT / "tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)

A0 = [
    ("es_a0_repeat_hola", "Приветствие", "Hola.", "Привет.", ["Hola.", "Hola"]),
    ("es_a0_repeat_gracias", "Благодарность", "Gracias.", "Спасибо.", ["Gracias.", "Gracias"]),
    ("es_a0_repeat_me_llamo", "Представление", "Me llamo Ana.", "Меня зовут Ана.", ["Me llamo Ana.", "Me llamo Ana"]),
    ("es_a0_repeat_buenas_tardes", "Добрый день", "Buenas tardes.", "Добрый день.", ["Buenas tardes."]),
    ("es_a0_repeat_adios", "Прощание", "Adiós.", "До свидания.", ["Adiós.", "Adiós"]),
    ("es_a0_repeat_por_favor", "Вежливость", "Por favor.", "Пожалуйста.", ["Por favor."]),
    ("es_a0_repeat_de_nada", "Ответ на спасибо", "De nada.", "Не за что.", ["De nada."]),
    ("es_a0_repeat_si_gracias", "Согласие", "Sí, gracias.", "Да, спасибо.", ["Sí, gracias."]),
    ("es_a0_repeat_no_gracias", "Отказ", "No, gracias.", "Нет, спасибо.", ["No, gracias."]),
    ("es_a0_repeat_hasta_luego", "До встречи", "Hasta luego.", "До скорого.", ["Hasta luego."]),
]

A1 = [
    ("es_a1_repeat_cafe", "Заказ в кафе", "Quiero un café, por favor.", "Я хочу кофе, пожалуйста.", ["Quiero un café, por favor.", "Quiero un café."]),
    ("es_a1_repeat_bano", "Спросить дорогу", "¿Dónde está el baño?", "Где туалет?", ["¿Dónde está el baño?"]),
    ("es_a1_repeat_ayuda", "Попросить помощь", "Necesito ayuda, por favor.", "Мне нужна помощь, пожалуйста.", ["Necesito ayuda, por favor."]),
    ("es_a1_repeat_vivo_madrid", "Где живёшь", "Vivo en Madrid.", "Я живу в Мадриде.", ["Vivo en Madrid."]),
    ("es_a1_repeat_veinte", "Возраст", "Tengo veinte años.", "Мне двадцать лет.", ["Tengo veinte años."]),
    ("es_a1_repeat_cuanto_cuesta", "Цена", "¿Cuánto cuesta?", "Сколько стоит?", ["¿Cuánto cuesta?"]),
    ("es_a1_repeat_billete", "Билет", "Un billete, por favor.", "Билет, пожалуйста.", ["Un billete, por favor."]),
    ("es_a1_repeat_me_gusta_te", "Предпочтения", "Me gusta el té.", "Мне нравится чай.", ["Me gusta el té."]),
    ("es_a1_repeat_hora", "Время", "¿Qué hora es?", "Который час?", ["¿Qué hora es?"]),
    ("es_a1_repeat_aprendiendo", "О себе", "Estoy aprendiendo español.", "Я учу испанский.", ["Estoy aprendiendo español."]),
    ("es_a1_repeat_repetir", "Переспросить", "¿Puede repetir, por favor?", "Можете повторить, пожалуйста?", ["¿Puede repetir, por favor?"]),
    ("es_a1_repeat_no_entiendo", "Не понимаю", "No entiendo.", "Я не понимаю.", ["No entiendo."]),
    ("es_a1_repeat_poco_espanol", "Уровень", "Hablo un poco de español.", "Я немного говорю по-испански.", ["Hablo un poco de español."]),
    ("es_a1_repeat_donde_vives", "Вопрос о жилье", "¿Dónde vives?", "Где ты живёшь?", ["¿Dónde vives?", "Vivo en..."]),
    ("es_a1_repeat_agua", "Заказ воды", "Quiero agua, por favor.", "Я хочу воду, пожалуйста.", ["Quiero agua, por favor.", "Quiero un agua, por favor."]),
]


def write_task(task_id, category_id, level, order, title, display, meaning_ru, acceptable, notes=""):
    doc = {
        "schema_version": "1.0",
        "id": task_id,
        "category_id": category_id,
        "level": level,
        "type": "repeat_phrase",
        "target_language": "es",
        "title": title,
        "prompt_ru": "Скажи по-испански:",
        "display_text": display,
        "expected_meaning_ru": meaning_ru,
        "acceptable_answers": acceptable,
        "evaluation_notes": notes or f"Ожидается естественное произношение: {display}",
        "max_attempts": 3,
        "order": order,
    }
    rel = f"tasks/{task_id}.json"
    (TASKS_DIR / f"{task_id}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return task_id, rel


index = {
    "version": "1.0.0",
    "generated_at": "2026-05-24T12:00:00Z",
    "categories": {
        "es_a0": {
            "id": "es_a0",
            "title": "ES A0 Speaking",
            "level": "A0",
            "order": 0,
            "task_ids": [],
        },
        "es_a1": {
            "id": "es_a1",
            "title": "ES A1 Speaking",
            "level": "A1",
            "order": 1,
            "task_ids": [],
        },
    },
    "tasks": {},
}

for i, row in enumerate(A0, start=1):
    tid, rel = write_task(row[0], "es_a0", "A0", i * 10, row[1], row[2], row[3], row[4])
    index["categories"]["es_a0"]["task_ids"].append(tid)
    index["tasks"][tid] = rel

for i, row in enumerate(A1, start=1):
    tid, rel = write_task(row[0], "es_a1", "A1", i * 10, row[1], row[2], row[3], row[4])
    index["categories"]["es_a1"]["task_ids"].append(tid)
    index["tasks"][tid] = rel

(ROOT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Generated {len(index['tasks'])} speaking tasks")
