#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-off generator for chapter 107 questions (validator-safe)."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / (
    "chapters/107.es.grammar.non_finite_forms_periphrases."
    "infinitive_after_prepositions_conjunctions/03-questions.json"
)

BLOCKS = [
    "b1_theory_core_prep_infinitive_shared_subject",
    "b2_theory_temporal_al_antes_despues_de",
    "b3_theory_para_sin_por_lugar_infinitive",
    "b4_theory_que_clauses_vs_prep_infinitive",
    "b5_theory_verb_prep_patterns_infinitive",
    "b6_theory_pitfalls_and_style",
]

questions = []
n = 0
prompts = set()
long_ans = set()


def nid():
    global n
    n += 1
    return f"q{n:03d}"


def reg(q):
    p = q["prompt"].strip()
    if q["type"] != "reorder":
        if p in prompts:
            raise SystemExit(f"duplicate prompt: {p[:80]}")
        prompts.add(p)
    qt = q["type"]
    if qt in ("mcq_single", "error_spotting"):
        cmap = {c["id"]: c["text"].strip() for c in q["choices"]}
        texts = list(cmap.values())
        if len(texts) != len(set(texts)):
            raise SystemExit(f"dup choice texts {q['id']}")
        ca = cmap[q["correct_answer"]]
        if len(ca) > 10 and ca in long_ans:
            raise SystemExit(f"dup long mcq/err {q['id']}")
        if len(ca) > 10:
            long_ans.add(ca)
    elif qt == "fill_blank":
        ca = q["correct_answer"].strip()
        if len(ca) > 10 and ca in long_ans:
            raise SystemExit(f"dup long fill {q['id']}")
        if len(ca) > 10:
            long_ans.add(ca)
    elif qt == "reorder":
        ca = q["correct_answer"].strip()
        if len(ca) > 10 and ca in long_ans:
            raise SystemExit(f"dup long reorder {q['id']}")
        if len(ca) > 10:
            long_ans.add(ca)
    questions.append(q)


def mcq(bid, prompt, opts, corr, expl, diff=2):
    reg(
        {
            "id": nid(),
            "type": "mcq_single",
            "prompt": prompt,
            "theory_block_id": bid,
            "difficulty": diff,
            "choices": [
                {"id": k, "text": t, "feedback": fb} for (k, t, fb) in opts
            ],
            "correct_answer": corr,
            "explanation": expl,
            "tags": [],
        }
    )


def fb(bid, prompt, ans, expl, diff=2):
    reg(
        {
            "id": nid(),
            "type": "fill_blank",
            "prompt": prompt,
            "theory_block_id": bid,
            "difficulty": diff,
            "correct_answer": ans,
            "explanation": expl,
            "tags": [],
        }
    )


def tf(bid, prompt, ans, expl, diff=2):
    reg(
        {
            "id": nid(),
            "type": "true_false",
            "prompt": prompt,
            "theory_block_id": bid,
            "difficulty": diff,
            "correct_answer": ans,
            "explanation": expl,
            "tags": [],
        }
    )


def err(bid, prompt, opts, corr, expl, diff=3):
    reg(
        {
            "id": nid(),
            "type": "error_spotting",
            "prompt": prompt,
            "theory_block_id": bid,
            "difficulty": diff,
            "choices": [
                {"id": k, "text": t, "feedback": fb} for (k, t, fb) in opts
            ],
            "correct_answer": corr,
            "explanation": expl,
            "tags": [],
        }
    )


def reorder(bid, words, expl, diff=3):
    reg(
        {
            "id": nid(),
            "type": "reorder",
            "prompt": "Расставьте слова в правильном порядке:",
            "theory_block_id": bid,
            "difficulty": diff,
            "choices": [{"id": x, "text": w, "feedback": ""} for x, w in zip("abcd", words)],
            "correct_answer": " ".join(words),
            "explanation": expl,
            "tags": [],
        }
    )


# ===== b1 =====
B = BLOCKS[0]
mcq(
    B,
    "В нейтральной норме после простого предлога с тем же субъектом в испанском ставят:",
    [
        ("a", "инфинитив", "Да."),
        ("b", "настоящее время 1-го лица без придаточного", "Нет."),
        ("c", "повелительное наклонение без контекста обращения", "Нет."),
        ("d", "сослагательное на *-ra/-se* сразу после предлога", "Нет."),
    ],
    "a",
    "Базовое правило главы: предлог + инфинитив при совпадении субъекта.",
)
mcq(
    B,
    "В цепочке *Vengo a ___ contigo* при одном «я» логичнее всего:",
    [
        ("a", "ayudar", "Да: *a* + инфинитив."),
        ("b", "ayudo", "Нет."),
        ("c", "ayudaba", "Нет."),
        ("d", "ayudando", "Нет."),
    ],
    "a",
    "После *a* в значении цели — инфинитив.",
)
mcq(
    B,
    "Фраза *antes de salir* при типичном субъекте означает:",
    [
        ("a", "«до того как (сам) выйду / выйдешь…» в связке с главным сказуемым", "Да."),
        ("b", "«потому что я выхожу»", "Нет."),
        ("c", "«если только я выйду»", "Нет."),
        ("d", "«пока я не вышел в прошлом» как единственное чтение", "Нет."),
    ],
    "a",
    "*antes de* + инфинитив — временная рамка при том же действующем лице.",
)
mcq(
    B,
    "Конструкция *necesito tiempo para …* с целью «подумать» чаще продолжается как:",
    [
        ("a", "*para pensar*", "Да."),
        ("b", "*para pienso*", "Нет."),
        ("c", "*para pensaba*", "Нет."),
        ("d", "*para que pensar*", "Нет."),
    ],
    "a",
    "*para* + инфинитив выражает цель при совпадении субъекта.",
)
fb(
    B,
    "Вставьте одно слово: **Aprendió a ___ en metro.** (подсказка: двигаться самостоятельно — возвратный инф. на *-er*)",
    "moverse",
    "После *a* — инфинитив; возвратное *moverse* уместно в значении передвижения.",
)
fb(
    B,
    "Вставьте одно слово: **Salieron sin ___.** (подсказка: прощаться — инф. на *-ar*, другая форма)",
    "despedirse",
    "*sin* + инфинитив.",
)
tf(
    B,
    "Сочетание *después de llego* выглядит нейтрально и учебно нормальным.",
    "false",
    "Нужно *después de llegar*.",
)
tf(
    B,
    "В модели *quiero saber* второй глагол стоит в инфинитиве.",
    "true",
    "Стандартная коллокация.",
)
err(
    B,
    "Где нет ошибки «предлог + спряжение»?",
    [
        ("a", "Vino a pedir perdón.", "Да."),
        ("b", "Vino a pide perdón.", "Нет."),
        ("c", "Vino a pedía perdón.", "Нет."),
        ("d", "Vino a pidió perdón.", "Нет."),
    ],
    "a",
    "После *a* — инфинитив.",
)
err(
    B,
    "Выберите исправление цепочки *sin + глагол* при одном субъекте.",
    [
        ("a", "Se marchó sin decir adiós.", "Да."),
        ("b", "Se marchó sin dice adiós.", "Нет."),
        ("c", "Se marchó sin que decir adiós.", "Нет."),
        ("d", "Se marchó sin decía adiós.", "Нет."),
    ],
    "a",
    "*sin* + инфинитив.",
)
reorder(
    B,
    ["Vengo", "a", "escucharte", "con", "calma", "."],
    "После *a* — инфинитив с клитиком.",
)

# ===== b2 =====
B = BLOCKS[1]
mcq(
    B,
    "Слитная форма перед существительным в шаблоне момента *… llegar la tarde* — это:",
    [
        ("a", "*al* (сочетание предлога и артикля)", "Да."),
        ("b", "*a el* как две отдельные части в этом шаблоне", "Нет."),
        ("c", "*del*", "Нет."),
        ("d", "*el a*", "Нет."),
    ],
    "a",
    "*al* + инфинитив — устойчивый маркер.",
)
mcq(
    B,
    "Смысл *al abrir la ventana* ближе всего к:",
    [
        ("a", "моменту, связанному с действием открытия", "Да."),
        ("b", "чистой причине как *porque*", "Нет."),
        ("c", "условию *если только*", "Нет."),
        ("d", "просьбе *пожалуйста открой*", "Нет."),
    ],
    "a",
    "Временная связка *al* + инфинитив.",
)
mcq(
    B,
    "После *antes de* в модели одного субъекта стандартно идёт:",
    [
        ("a", "инфинитив", "Да."),
        ("b", "форма *antes de que* без глагола", "Нет."),
        ("c", "повелительное *sal* без адресата в той же цепочке", "Нет."),
        ("d", "причастие *salido* сразу после *de*", "Нет."),
    ],
    "a",
    "*antes de* + инфинитив.",
)
mcq(
    B,
    "*Después de comer* без дополнительных маркеров обычно читается как:",
    [
        ("a", "«после еды (самого субъекта)»", "Да."),
        ("b", "«потому что ели»", "Нет."),
        ("c", "«прежде чем вообще ели»", "Нет."),
        ("d", "«чтобы они поели»", "Нет."),
    ],
    "a",
    "Временная рамка с инфинитивом.",
)
fb(
    B,
    "Вставьте одно слово: **Al ___, oyó las campanas.** (подсказка: прибыть — инф. на *-ar*, не *llegó*)",
    "llegar",
    "*al* + инфинитив задаёт момент.",
)
fb(
    B,
    "Вставьте одно слово: **___ de comer, cerraron el comedor.** (подсказка: частица «после» одним словом, не *antes*)",
    "Después",
    "Связка *después de* + инфинитив.",
)
tf(
    B,
    "*Al llegar* можно заменить на *a llegar* в той же норме.",
    "false",
    "Нужна слитная форма *al*.",
)
tf(
    B,
    "*Después de estudiar* допустимо при том же субъекте.",
    "true",
    "Инфинитив после *después de*.",
)
err(
    B,
    "Где временная рамка с инфинитивом оформлена верно?",
    [
        ("a", "Después de leer el correo, respondió.", "Да."),
        ("b", "Después de lee el correo, respondió.", "Нет."),
        ("c", "Después de leyendo el correo, respondió.", "Нет."),
        ("d", "Después de leyó el correo, respondió.", "Нет."),
    ],
    "a",
    "*después de* + инфинитив.",
)
err(
    B,
    "Где корректно *al* + инфинитив?",
    [
        ("a", "Al oír la noticia, se quedó en silencio.", "Да."),
        ("b", "A el oír la noticia, se quedó en silencio.", "Нет."),
        ("c", "Al oye la noticia, se quedó en silencio.", "Нет."),
        ("d", "Al oyendo la noticia, se quedó en silencio.", "Нет."),
    ],
    "a",
    "*al oír* — норма.",
)
reorder(
    B,
    ["Antes", "de", "firmar", ",", "lee", "el", "contrato", "."],
    "Сначала обстоятельство *antes de firmar*, затем главное; порядок слов испанский.",
)

# ===== b3 =====
B = BLOCKS[2]
mcq(
    B,
    "В значении «без действия» при одном субъекте чаще используют:",
    [
        ("a", "*sin* + инфинитив", "Да."),
        ("b", "*sin que* + инфинитив", "Нет."),
        ("c", "*sin* + настоящее время без *que*", "Нет."),
        ("d", "*sin de* + инфинитив", "Нет."),
    ],
    "a",
    "Базовая схема *sin* + инфинитив.",
)
mcq(
    B,
    "*Para* + инфинитив в *estudio para aprobar* выражает:",
    [
        ("a", "цель при том же субъекте", "Да."),
        ("b", "мотив «потому что экзамен трудный»", "Нет."),
        ("c", "просьбу к другому лицу", "Нет."),
        ("d", "условие «только если сдам»", "Нет."),
    ],
    "a",
    "Цель — *para* + инфинитив.",
)
mcq(
    B,
    "Оценочный мотив *por ser tan claro* построен как:",
    [
        ("a", "*por* + инфинитив", "Да."),
        ("b", "*para* + инфинитив в той же оценочной рамке", "Нет, стилистически другое."),
        ("c", "*porque* + инфинитив", "Нет."),
        ("d", "*por* + причастие без вспомогательного глагола", "Нет."),
    ],
    "a",
    "*por* + инфинитив в мотивной рамке.",
)
mcq(
    B,
    "*En vez de discutir* — это:",
    [
        ("a", "замена действия инфинитивом", "Да."),
        ("b", "придаточное с *que* без глагола", "Нет."),
        ("c", "сравнение прилагательных", "Нет."),
        ("d", "вопрос с перестановкой", "Нет."),
    ],
    "a",
    "*en vez de* + инфинитив.",
)
fb(
    B,
    "Вставьте одно слово: **Lo hizo sin ___.** (подсказка: глагол на *-er* в значении «нехотя», не *decir*)",
    "querer",
    "*sin querer* — устойчивое «нечаянно».",
)
fb(
    B,
    "Вставьте одно слово: **Vine para ___.** (подсказка: помогать — инф. на *-ar*)",
    "ayudar",
    "*para* + инфинитив цели.",
)
tf(
    B,
    "*Para que entender* — нормальная замена *para entender*.",
    "false",
    "Для «чтобы понял ты» — *para que entiendas*; *para entender* — другая модель.",
)
tf(
    B,
    "*Sin decir nada* — типичная связка при одном субъекте.",
    "true",
    "*sin* + инфинитив.",
)
err(
    B,
    "Где корректно выражена замена действия?",
    [
        ("a", "En lugar de gritar, respiró hondo.", "Да."),
        ("b", "En lugar de grita, respiró hondo.", "Нет."),
        ("c", "En lugar de gritando, respiró hondo.", "Нет."),
        ("d", "En lugar de que gritar, respiró hondo.", "Нет."),
    ],
    "a",
    "*en lugar de* + инфинитив.",
)
err(
    B,
    "Где нет ошибки в мотивной рамке?",
    [
        ("a", "Por ser tan puntual, confío en él.", "Да."),
        ("b", "Para ser tan puntual, confío en él.", "Нет в этой мотивной рамке."),
        ("c", "Por ser tan puntualmente, confío en él.", "Нет."),
        ("d", "Por ser puntualidad, confío en él.", "Нет."),
    ],
    "a",
    "*por ser* + прилагательное — мотив.",
)
reorder(
    B,
    ["Sin", "pensarlo", "dos", "veces", ",", "aceptó", "."],
    "Оборот *sin pensarlo* + инфинитив в устойчивом выражении.",
)

# ===== b4 =====
B = BLOCKS[3]
mcq(
    B,
    "Если нужно «прежде чем он войдёт», ближе к норме:",
    [
        ("a", "*antes de que* + форма придаточного, не инфинитив сразу после *que*", "Да."),
        ("b", "*antes de que llegar*", "Нет."),
        ("c", "*antes de él entra*", "Нет."),
        ("d", "*antes de entra*", "Нет."),
    ],
    "a",
    "*antes de que* ведёт придаточное со спряжением.",
)
mcq(
    B,
    "*Para que entiendas* отличается от *para entender* тем, что:",
    [
        ("a", "в первом явно другой адресат действия «понимать»", "Да."),
        ("b", "в обоих одинаковый субъект без различий", "Нет."),
        ("c", "второй всегда прошедшее время", "Нет."),
        ("d", "первый запрещён в разговорной речи", "Нет."),
    ],
    "a",
    "*para que* + сослагательное vs *para* + инфинитив.",
)
mcq(
    B,
    "*Sin que nadie lo supiera* противопоставляется *sin saberlo* тем, что:",
    [
        ("a", "в первом придаточное с другим субъектом/фокусом «чтобы не знали»", "Да."),
        ("b", "оба всегда равны по субъекту", "Нет."),
        ("c", "второй всегда требует *que*", "Нет."),
        ("d", "первый всегда разговорный жаргон", "Нет."),
    ],
    "a",
    "Контраст *sin que* vs *sin* + инфинитив.",
)
mcq(
    B,
    "После *antes de que* в учебной норме не ставят:",
    [
        ("a", "инфинитив сразу после *que*", "Да, это маркер ошибки."),
        ("b", "союз *que*", "Нет, он нужен."),
        ("c", "существительное как субъект придаточного", "Нет."),
        ("d", "глагол в форме придаточного", "Нет."),
    ],
    "a",
    "*antes de que* + спряжение, не инфинитив.",
)
fb(
    B,
    "Вставьте одно слово: **Cierra la ventana antes de que ___.** (подсказка: форма сослагательного 3 л. ед. глагола *entrar*, не инфинитив)",
    "entre",
    "После *antes de que* — спряжение в придаточном, не инфинитив сразу после *que*.",
)
fb(
    B,
    "Вставьте одно слово: **Te lo explico para que ___.** (подсказка: 2 л. ед. сослагательное от *entender*, не инфинитив)",
    "entiendas",
    "*para que* + форма придаточного для другого субъекта.",
)
tf(
    B,
    "После *antes de que* нормально писать *antes de que llegar*.",
    "false",
    "Нужна спряжённая форма, не инфинитив сразу после *que*.",
)
tf(
    B,
    "*Para entenderlo* может выражать цель говорящего без смены субъекта на «ты».",
    "true",
    "*para* + инфинитив при том же субъекте.",
)
err(
    B,
    "Где корректно оформлено *para que* + придаточное?",
    [
        ("a", "Lo repito para que lo recuerdes.", "Да."),
        ("b", "Lo repito para que lo recordar.", "Нет."),
        ("c", "Lo repito para que recordando.", "Нет."),
        ("d", "Lo repito para que lo recordaste.", "Нет."),
    ],
    "a",
    "После *para que* — спряжённая форма.",
)
err(
    B,
    "Где *sin que* уместнее, чем *sin* + инфинитив?",
    [
        ("a", "Se fue sin que nadie lo viera.", "Да: чужое действие/перспектива."),
        ("b", "Se fue sin que nadie lo ver.", "Нет."),
        ("c", "Se fue sin que nadie verlo.", "Нет."),
        ("d", "Se fue sin que ver nadie.", "Нет."),
    ],
    "a",
    "*sin que* + сослагательное при «чтобы не увидели».",
)
reorder(
    B,
    ["Cierra", "la", "ventana", "antes", "de", "salir", ",", "por", "favor", "."],
    "Сначала императив, затем обстоятельство *antes de salir*.",
)

# ===== b5 =====
B = BLOCKS[4]
mcq(
    B,
    "Устойчивая коллокация: «настаивать на том, чтобы (самому) платить» — это:",
    [
        ("a", "*insistir en pagar*", "Да."),
        ("b", "*insistir a pagar*", "Нет."),
        ("c", "*insistir de pagar*", "Нет."),
        ("d", "*insistir para pagar*", "Нет."),
    ],
    "a",
    "Глагол + предлог *en* + инфинитив.",
)
mcq(
    B,
    "«Думать о том, чтобы переехать» ближе всего к:",
    [
        ("a", "*pensar en mudarse*", "Да."),
        ("b", "*pensar de mudarse*", "Нет."),
        ("c", "*pensar por mudarse*", "Нет."),
        ("d", "*pensar mudarse*", "Нет."),
    ],
    "a",
    "*pensar en* + инфинитив.",
)
mcq(
    B,
    "Перифраста «только что сделал» строится как:",
    [
        ("a", "*acabar de* + инфинитив", "Да."),
        ("b", "*acabar* + причастие без *de*", "Нет."),
        ("c", "*acabar en* + инфинитив", "Нет."),
        ("d", "*acabar que* + инфинитив", "Нет."),
    ],
    "a",
    "Устойчивый триплет.",
)
mcq(
    B,
    "«Бросить курить» — устойчиво:",
    [
        ("a", "*dejar de fumar*", "Да."),
        ("b", "*dejar fumar*", "Нет без *de*."),
        ("c", "*dejar en fumar*", "Нет."),
        ("d", "*dejar para fumar*", "Нет."),
    ],
    "a",
    "*dejar de* + инфинитив.",
)
fb(
    B,
    "Вставьте одно слово: **Volvió a ___.** (подсказка: пробовать — инф. на *-ar*)",
    "intentar",
    "*volver a* + инфинитив.",
)
fb(
    B,
    "Вставьте одно слово: **Trató de ___.** (подсказка: объяснять — инф. на *-ar*)",
    "explicar",
    "*tratar de* + инфинитив.",
)
tf(
    B,
    "*Pensar en hacerlo* — возможная норма при фиксированном предлоге.",
    "true",
    "Триплет глагол + предлог + инфинитив.",
)
tf(
    B,
    "*Insistir a pagar* — нейтральная норма.",
    "false",
    "Нужно *insistir en pagar*.",
)
err(
    B,
    "Где нет ошибки в предлоге?",
    [
        ("a", "Sueña con vivir en otro país.", "Да: *soñar con* + инфинитив."),
        ("b", "Sueña de vivir en otro país.", "Нет."),
        ("c", "Sueña por vivir en otro país.", "Нет."),
        ("d", "Sueña en vivir en otro país.", "Нет."),
    ],
    "a",
    "Фиксированный предлог у *soñar*.",
)
err(
    B,
    "Где корректно *volver a* + инфинитив?",
    [
        ("a", "Volvió a llamar más tarde.", "Да."),
        ("b", "Volvió a llama más tarde.", "Нет."),
        ("c", "Volvió a llamando más tarde.", "Нет."),
        ("d", "Volvió a llamó más tarde.", "Нет."),
    ],
    "a",
    "*volver a* + инфинитив.",
)
reorder(
    B,
    ["Insistió", "en", "pagar", "la", "cuenta", "él", "solo", "."],
    "Схема *insistir en* + инфинитив в середине высказывания.",
)

# ===== b6 =====
B = BLOCKS[5]
mcq(
    B,
    "Стиль B2: длинная цепочка только инфинитивов без связок обычно:",
    [
        ("a", "выглядит тяжеловесно и менее связно", "Да."),
        ("b", "считается лучшим признаком владения языком", "Нет."),
        ("c", "заменяет пунктуацию полностью", "Нет."),
        ("d", "обязательна в официальных текстах", "Нет."),
    ],
    "a",
    "Чередование конструкций улучшает стиль.",
)
mcq(
    B,
    "После *sin que* в норме ожидается:",
    [
        ("a", "спряжённая форма в придаточном, а не инфинитив сразу после *que*", "Да."),
        ("b", "инфинитив сразу после *que*", "Нет."),
        ("c", "только существительное без глагола", "Нет."),
        ("d", "повелительное наклонение без субъекта", "Нет."),
    ],
    "a",
    "*sin que* ведёт придаточное со спряжением.",
)
mcq(
    B,
    "Перфектный инфинитив *después de haber hablado* допустим как:",
    [
        ("a", "временное обстоятельство с завершённостью до главного действия", "Да."),
        ("b", "замена любому *antes de que*", "Нет."),
        ("c", "вопросительная форма без изменений", "Нет."),
        ("d", "союз *y* между двумя главными", "Нет."),
    ],
    "a",
    "Сложный инфинитив в обстоятельстве времени.",
)
mcq(
    B,
    "Русская калькa «после того как + инфинитив» в испанском чаще переносится как:",
    [
        ("a", "*después de* + инфинитив или придаточное с *después de que*", "Да."),
        ("b", "*después que* + инфинитив сразу", "Нет."),
        ("c", "*después* + настоящее без предлога всегда", "Нет."),
        ("d", "*después de que* + инфинитив сразу после *que*", "Нет."),
    ],
    "a",
    "Не копировать русский порядок буквально.",
)
fb(
    B,
    "Вставьте одно слово: **Después de haber ___, firmó el acta.** (подсказка: обсуждать — participio, не инфинитив)",
    "discutido",
    "Перфектный инфинитив *haber* + participio.",
)
fb(
    B,
    "Вставьте одно слово: **No quiso ir sin ___.** (подсказка: прощаться — возвратный инф. на *-ar*)",
    "despedirse",
    "*sin* + инфинитив компактнее, чем лишний *sin que*.",
)
tf(
    B,
    "*Sin que saber* — нормальная нейтральная форма.",
    "false",
    "Нужно *sin saber* или *sin que supiera* в придаточном.",
)
tf(
    B,
    "Перегруз *sin que* без смысла «чужого» действия может ухудшить стиль.",
    "true",
    "Стилистика: предпочитать *sin* + инфинитив, когда можно.",
)
err(
    B,
    "Где компактная норма с *sin* + инфинитив?",
    [
        ("a", "Salió sin mirar atrás.", "Да."),
        ("b", "Salió sin mira atrás.", "Нет."),
        ("c", "Salió sin que mirar atrás.", "Нет."),
        ("d", "Salió sin mirando atrás.", "Нет."),
    ],
    "a",
    "Один субъект — *sin* + инфинитив.",
)
err(
    B,
    "Где корректен перфектный инфинитив во временной рамке?",
    [
        ("a", "Después de haber leído el informe, decidió actuar.", "Да."),
        ("b", "Después de haber leer el informe, decidió actuar.", "Нет."),
        ("c", "Después de haber leyendo el informe, decidió actuar.", "Нет."),
        ("d", "Después de haber leyó el informe, decidió actuar.", "Нет."),
    ],
    "a",
    "*haber* + participio в обстоятельстве.",
)
reorder(
    B,
    ["Después", "de", "hablar", "con", "ella", ",", "cambió", "de", "idea", "."],
    "Временная рамка *después de hablar* + главное сказуемое.",
)

if len(questions) != 66:
    raise SystemExit(f"expected 66 questions, got {len(questions)}")

OUT.write_text(
    json.dumps({"questions": questions}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Wrote {len(questions)} questions to {OUT}")
