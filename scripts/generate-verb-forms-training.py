#!/usr/bin/env python3
"""
Генерация артефактов verb_forms (LLM). Опционально: автозапуск llama-server.

  VERB_FORMS_ENSURE_LLAMA=auto — если задан LLAMACPP_START_CMD_VERB или LLAMACPP_START_CMD,
    а LLAMACPP_URL (или AI_URL) не отвечает на /v1/models и /health, выполнить команду и ждать готовности.
  VERB_FORMS_ENSURE_LLAMA=0 — не трогать сервер.

  LLAMACPP_START_CMD_VERB — команда запуска только для этого скрипта (удобно задать llama-server … -n 16384 …).

  LLAMACPP_START_MAX_WAIT_SEC — ожидание готовности после автозапуска (по умолчанию здесь 120, если не задано).

  VERB_FORMS_CHUNK_VALIDATE_RETRIES — сколько раз перегенерировать один HTTP-чанк при ошибке семантической валидации
    (не совпал surface_form с options и т.д.); по умолчанию 8. CLI: --chunk-validate-retries.

На llama-server для длинного JSON обычно нужен лимит генерации не ниже VERB_FORMS_MAX_TOKENS (флаг -n / --predict).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

EXPECTED_SCOPES = [
    "es.presente.indicativo",
    "es.preterito_imperfecto.indicativo",
    "es.preterito_indefinido.indicativo",
    "es.futuro_simple.indicativo",
    "es.condicional_simple.indicativo",
    "es.preterito_perfecto_compuesto.indicativo",
    "es.preterito_pluscuamperfecto.indicativo",
    "es.preterito_anterior.indicativo",
    "es.futuro_perfecto.indicativo",
    "es.condicional_perfecto.indicativo",
    "es.presente.subjuntivo",
    "es.preterito_imperfecto.subjuntivo",
    "es.futuro_simple.subjuntivo",
    "es.preterito_perfecto.subjuntivo",
    "es.preterito_pluscuamperfecto.subjuntivo",
    "es.futuro_perfecto.subjuntivo",
]

EXPECTED_SLOTS = [
    ("1", "singular"),
    ("2", "singular"),
    ("3", "singular"),
    ("1", "plural"),
    ("2", "plural"),
    ("3", "plural"),
]

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_CYAN = "\033[36m"

_PROGRESS: Optional["ProgressLine"] = None


class ProgressLine:
    def __init__(self):
        self.enabled = bool(sys.stdout.isatty())
        self.total_hint = 0
        self.processed = 0
        self.current_lemma = ""
        self.chunk_label = ""
        self.attempt = 0
        self.attempt_max = 0
        self.stream_chars = 0
        self.stream_tail = ""
        self.started_at = time.time()

    def set_total_hint(self, n: int) -> None:
        if n > 0:
            self.total_hint = max(self.total_hint, n)
            self.render()

    def set_processed(self, n: int) -> None:
        self.processed = max(0, n)
        self.render()

    def set_current_lemma(self, lemma: str) -> None:
        self.current_lemma = lemma or ""
        self.render()

    def set_chunk(self, label: str, attempt: int = 0, attempt_max: int = 0) -> None:
        self.chunk_label = label or ""
        self.attempt = max(0, attempt)
        self.attempt_max = max(0, attempt_max)
        self.render()

    def update_stream(self, text: str) -> None:
        self.stream_chars = len(text or "")
        self.stream_tail = _compact_tail(text or "", 36)
        self.render()

    def clear_stream(self) -> None:
        self.stream_chars = 0
        self.stream_tail = ""
        self.render()

    def clear_chunk(self) -> None:
        self.chunk_label = ""
        self.attempt = 0
        self.attempt_max = 0
        self.render()

    def before_log(self) -> None:
        if self.enabled:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()

    def after_log(self) -> None:
        self.render()

    def finalize(self) -> None:
        if self.enabled:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()

    def _eta_text(self) -> str:
        if self.processed <= 0 or self.total_hint <= 0 or self.processed >= self.total_hint:
            return "--:--"
        elapsed = max(1.0, time.time() - self.started_at)
        rate = self.processed / elapsed
        if rate <= 0:
            return "--:--"
        sec = int((self.total_hint - self.processed) / rate)
        m, s = divmod(max(0, sec), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _bar(self) -> str:
        width = 24
        if self.total_hint > 0:
            ratio = min(1.0, self.processed / max(1, self.total_hint))
            done = int(width * ratio)
            return "[" + "#" * done + "-" * (width - done) + "]"
        pulse = int((time.time() * 2) % width)
        return "[" + "-" * pulse + ">" + "-" * max(0, width - pulse - 1) + "]"

    def render(self) -> None:
        if not self.enabled:
            return
        total_txt = str(self.total_hint) if self.total_hint > 0 else "?"
        eta = self._eta_text()
        lemma = self.current_lemma or "-"
        attempt = ""
        if self.attempt_max > 0:
            attempt = f" try {self.attempt}/{self.attempt_max}"
        llm = ""
        if self.stream_chars > 0:
            llm = f" | LLM {self.stream_chars}ch …{self.stream_tail}"
        chunk = f" | {self.chunk_label}{attempt}" if self.chunk_label else ""
        msg = f"{ANSI_CYAN}{self._bar()} {self.processed}/{total_txt} ETA {eta} | lemma={lemma}{chunk}{llm}{ANSI_RESET}"
        sys.stdout.write("\r\033[2K" + msg)
        sys.stdout.flush()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str, color: str = ""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if _PROGRESS is not None:
        _PROGRESS.before_log()
    if color:
        print(f"{color}{ts}: {msg}{ANSI_RESET}", flush=True)
    else:
        print(f"{ts}: {msg}", flush=True)
    if _PROGRESS is not None:
        _PROGRESS.after_log()


def log(msg: str):
    _log(msg)


def log_info(msg: str):
    _log(msg, ANSI_CYAN)


def log_ok(msg: str):
    _log(msg, ANSI_GREEN)


def log_warn(msg: str):
    _log(msg, ANSI_YELLOW)


def log_err(msg: str):
    _log(msg, ANSI_RED)


def short_text(text: str, limit: int = 220) -> str:
    one = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(one) <= limit:
        return one
    return one[:limit] + "..."


def _compact_tail(text: str, limit: int = 50) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[-limit:]


def _stream_status(prefix: str, text: str) -> None:
    _ = prefix
    if _PROGRESS is not None:
        _PROGRESS.update_stream(text)
        return
    tail = _compact_tail(text, 50)
    msg = f"[verb-forms LLM] получаем ответ... {len(text)} симв ... {tail}"
    sys.stdout.write("\r" + ANSI_CYAN + msg + ANSI_RESET)
    sys.stdout.flush()


def _stream_finalize_line():
    if _PROGRESS is not None:
        _PROGRESS.clear_stream()
        return
    sys.stdout.write("\n")
    sys.stdout.flush()


def _emit_blocking_preview(prefix: str, content: str) -> None:
    """Индикатор как у stream, если ответ пришёл blocking-запросом (одна строка + перевод строки)."""
    if not (content or "").strip():
        return
    _stream_status(prefix, content)
    _stream_finalize_line()


def _max_output_tokens() -> int:
    """Лимит токенов на ответ; без этого llama-server часто режет JSON по умолчанию (~2k–4k)."""
    raw = os.environ.get("VERB_FORMS_MAX_TOKENS", "").strip()
    if not raw:
        return 16384
    try:
        n = int(raw)
    except ValueError:
        return 16384
    return max(2048, min(n, 200000))


def _scopes_per_llm_request() -> int:
    """Сколько scope за один HTTP-запрос.
    По умолчанию 4 → 16 scope / 4 = 4 батча на лемму. Меньше (1–2) — короче JSON, меньше обрезок на слабом llama
    (см. VERB_FORMS_SCOPES_PER_REQUEST=2 → 8 запросов)."""
    raw = os.environ.get("VERB_FORMS_SCOPES_PER_REQUEST", "").strip()
    if not raw:
        return 4
    try:
        n = int(raw)
    except ValueError:
        return 4
    return max(1, min(n, len(EXPECTED_SCOPES)))


def _chunk_scopes(scopes: List[str], size: int) -> List[List[str]]:
    return [scopes[i : i + size] for i in range(0, len(scopes), size)]


def _verb_forms_disable_stream() -> bool:
    return os.environ.get("VERB_FORMS_DISABLE_STREAM", "").strip().lower() in ("1", "true", "yes")


def _expected_json_min_chars(card_count: int) -> int:
    """Грубая нижняя граница размера ответа для полного массива карточек (сырой JSON)."""
    return max(500, card_count * 75)


class OutputTruncatedError(Exception):
    """Ответ обрезан по length или неполный массив — дробим батч, не тратим лишние полные ретраи."""



def _batch_inline_retries() -> int:
    """Сколько раз повторить тот же батч scopes перед дроблением пополам."""
    raw = os.environ.get("VERB_FORMS_BATCH_PARSE_RETRIES", "").strip()
    if not raw:
        return 2
    try:
        n = int(raw)
    except ValueError:
        return 2
    return max(1, min(n, 15))


def _chunk_validation_retries(cli_override: Optional[int]) -> int:
    """Сколько раз перегенерировать один HTTP-чанк при ошибке validate_cards_for_scopes (не весь глагол)."""
    if cli_override is not None:
        return max(1, min(int(cli_override), 50))
    raw = os.environ.get("VERB_FORMS_CHUNK_VALIDATE_RETRIES", "").strip()
    if not raw:
        return 8
    try:
        n = int(raw)
    except ValueError:
        return 8
    return max(1, min(n, 50))


def _batch_label(bi: int, total_b: int, scopes: List[str], split_depth: int) -> str:
    snip = ",".join(scopes[:3]) + ("…" if len(scopes) > 3 else "")
    depth = f" split_depth={split_depth}" if split_depth else ""
    return f"batch {bi}/{total_b}{depth} scopes=[{snip}]"


def _build_batch_messages(
    lemma: str,
    system_tpl: str,
    scopes_batch: List[str],
    bi: int,
    total_b: int,
) -> List[dict]:
    user = {
        "lemma": lemma,
        "expected_scopes": scopes_batch,
        "expected_slots": [{"person": p, "number": n} for p, n in EXPECTED_SLOTS],
        "format_note": "question_es_with_blank должен содержать пропуск и (lemma), например: '_ de Madrid. (tener)'",
        "quality_note": (
            "Для каждой карточки: испанская surface_form строго соответствует scope/лицу/числу; "
            "русский перевод грамматически верный (окончания, время, согласование); испанское предложение с пропуском осмысленное."
        ),
        "batch_index": bi,
        "batch_total": total_b,
    }
    return [
        {"role": "system", "content": system_tpl},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def _log_json_decode_failure(lemma: str, raw: str, err: JSONDecodeError) -> None:
    log_err(
        f"[llm] JSON decode lemma={lemma}: {err.msg} (line {err.lineno}, col {err.colno}, pos {err.pos})"
    )
    pos = int(err.pos) if err.pos is not None else 0
    span = 200
    lo = max(0, pos - span)
    hi = min(len(raw), pos + span)
    snippet = raw[lo:hi]
    caret = max(0, min(pos - lo, len(snippet)))
    log_err(f"[llm] fragment around pos {pos}:\n{snippet}\n{' ' * caret}^")
    try:
        dump = Path(tempfile.gettempdir()) / f"verb-forms-llm-raw-{lemma}.txt"
        dump.write_text(raw, encoding="utf-8")
        log_err(f"[llm] полный ответ сохранён: {dump}")
    except OSError as e:
        log_err(f"[llm] не удалось сохранить raw: {e}")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(v: str) -> str:
    t = str(v or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def parse_llm_json(raw: str):
    text = raw.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text or ""))


def validate_language_fields(scope: str, slot: str, c: dict) -> None:
    """Перевод на русском — с кириллицей; испанские поля без кириллицы."""
    ru = c.get("translation_ru_full") or ""
    if not has_cyrillic(ru):
        raise ValueError(
            f"translation_ru_full must contain Russian (Cyrillic) in {scope} {slot}"
        )
    for label, val in (
        ("surface_form", c.get("surface_form") or ""),
        ("question_es_with_blank", c.get("question_es_with_blank") or ""),
    ):
        if has_cyrillic(val):
            raise ValueError(f"Cyrillic forbidden in Spanish field {label} at {scope} {slot}: {short_text(val, 80)}")
    for i, opt in enumerate(c.get("options") or []):
        if has_cyrillic(str(opt)):
            raise ValueError(
                f"Cyrillic in Spanish option[{i}] at {scope} {slot}: {short_text(str(opt), 80)}"
            )


def normalize_card(card: dict) -> dict:
    scope = normalize_text(card.get("scope"))
    mood = normalize_text(card.get("mood"))
    tense = normalize_text(card.get("tense"))
    if not scope and mood and tense:
        scope = f"es.{tense}.{mood}"
    return {
        "scope": scope,
        "mood": mood,
        "tense": tense,
        "person": normalize_text(card.get("person")),
        "number": normalize_text(card.get("number")),
        "surface_form": normalize_text(card.get("surface_form")),
        "question_es_with_blank": str(card.get("question_es_with_blank", "")).strip(),
        "translation_ru_full": str(card.get("translation_ru_full", "")).strip(),
        "options": [normalize_text(x) for x in card.get("options", []) if str(x or "").strip()],
    }


def validate_cards_for_scopes(cards: List[dict], scopes: List[str]) -> None:
    """
    Строгая проверка набора карточек ровно для перечисленных scope (порядок как в батче LLM).
    Для полного артефакта: scopes == EXPECTED_SCOPES.
    """
    if len(set(scopes)) != len(scopes):
        raise ValueError("scopes list must not contain duplicates")
    need_total = len(scopes) * len(EXPECTED_SLOTS)
    if len(cards) != need_total:
        raise ValueError(
            f"expected exactly {need_total} cards ({len(scopes)} scopes × 6 persons), got {len(cards)}"
        )
    allowed = set(scopes)
    seen_by_scope = {scope: set() for scope in scopes}
    seen_q_ru_pairs: Dict[str, Set[Tuple[str, str]]] = {scope: set() for scope in scopes}
    for raw in cards:
        c = normalize_card(raw)
        scope = c["scope"]
        if scope not in allowed:
            raise ValueError(f"unexpected scope: {scope} (allowed: {scopes})")
        slot = f"{c['person']}:{c['number']}"
        if slot not in {f"{p}:{n}" for p, n in EXPECTED_SLOTS}:
            raise ValueError(f"unexpected slot {slot} for scope {scope}")
        if not c["mood"] or not c["tense"]:
            raise ValueError(f"empty mood/tense in {scope} {slot}")
        if not c["surface_form"]:
            raise ValueError(f"empty surface_form in {scope} {slot}")
        if not c["question_es_with_blank"] or not c["translation_ru_full"]:
            raise ValueError(f"empty question/translation in {scope} {slot}")
        validate_language_fields(scope, slot, c)
        opts = c["options"]
        if len(opts) != 4:
            raise ValueError(f"options must contain exactly 4 values in {scope} {slot}")
        if c["surface_form"] not in opts:
            raise ValueError(f"correct form is missing in options for {scope} {slot}")
        pair_key = (
            normalize_text(c["question_es_with_blank"]),
            normalize_text(c["translation_ru_full"]),
        )
        if pair_key in seen_q_ru_pairs[scope]:
            raise ValueError(f"duplicate question+translation_ru pair in {scope}")
        seen_q_ru_pairs[scope].add(pair_key)
        if slot in seen_by_scope[scope]:
            raise ValueError(f"duplicate slot {scope} {slot}")
        seen_by_scope[scope].add(slot)
    for scope in scopes:
        for person, number in EXPECTED_SLOTS:
            slot = f"{person}:{number}"
            if slot not in seen_by_scope[scope]:
                raise ValueError(f"missing slot {scope} {slot}")


def validate_artifact(lemma: str, cards: List[dict]):
    _ = lemma
    validate_cards_for_scopes(cards, EXPECTED_SCOPES)


def fetch_pending(api_base: str, token: str, limit: int, cursor: int, *, all_verbs: bool = False) -> dict:
    q = f"limit={limit}&cursor={cursor}"
    if all_verbs:
        q += "&all=1"
    url = f"{api_base.rstrip('/')}/api/internal/verb-training/pending?{q}"
    mode = "all infinitives (forms_gap_only off)" if all_verbs else "DB gap only (no verb_forms_dict yet)"
    log_info(f"[pending] GET {url}  [{mode}]")
    req = urllib.request.Request(url, method="GET")
    req.add_header("X-Service-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            log_ok(f"[pending] ok count={body.get('count', 0)} next_cursor={body.get('next_cursor', 0)}")
            return body
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(
            f"pending API HTTP error: status={e.code} url={url} body={body[:300]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            "pending API is unreachable.\n"
            f"URL: {url}\n"
            "Проверьте, что backend запущен и доступен, и что VERB_TRAINING_INTERNAL_API указывает на него."
        ) from e


def _openai_chat_stream(
    api_url: str,
    api_model: str,
    messages: List[dict],
    api_key: str,
    temperature: float,
    lemma: str,
    max_tokens: int,
    timeout: int = 600,
) -> Tuple[str, Optional[str]]:
    """OpenAI-совместимый поток (llama.cpp server): SSE data: {...}\\n.

    Читаем буфером: итерация по resp как по строкам часто даёт пустой текст, если сервер
    долго не шлёт \\n. Берём delta.content и запасной choices[0].message.content.
    Возвращает (text, finish_reason).
    """
    chat_url = api_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": api_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Content-Type": "application/json"}
    if str(api_key or "").strip():
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        chat_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    parts: List[str] = []
    finish_reason: Optional[str] = None
    message_fallback = ""
    buf = b""
    stream_done = False

    def consume_line(line: str) -> bool:
        """Обработать одну строку SSE; True = получен [DONE]."""
        nonlocal finish_reason, message_fallback
        s = line.strip()
        if not s:
            return False
        if s.startswith("data:"):
            s = s[5:].strip()
        if s == "[DONE]":
            return True
        try:
            data = json.loads(s)
        except Exception:
            return False
        choices = data.get("choices", [])
        if not choices:
            return False
        ch0 = choices[0]
        fr = ch0.get("finish_reason")
        if fr:
            finish_reason = fr
        delta = ch0.get("delta") or {}
        dchunk = delta.get("content") or ""
        if dchunk:
            parts.append(str(dchunk))
            _stream_status("[verb-forms LLM]", "".join(parts))
        msg = ch0.get("message")
        if isinstance(msg, dict):
            mc = msg.get("content")
            if isinstance(mc, str) and mc.strip():
                message_fallback = mc
        return False

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        while not stream_done:
            chunk = resp.read(8192)
            if not chunk:
                break
            buf += chunk
            while True:
                nl = buf.find(b"\n")
                if nl < 0:
                    break
                raw_line = buf[:nl]
                buf = buf[nl + 1 :]
                line = raw_line.decode("utf-8", errors="replace")
                if consume_line(line):
                    stream_done = True
                    break
        if buf.strip() and not stream_done:
            line = buf.decode("utf-8", errors="replace")
            consume_line(line)

    text = "".join(parts)
    if not text.strip() and message_fallback.strip():
        text = message_fallback
        log_info("[llm] stream: delta пустой, использован choices[0].message.content")
        _emit_blocking_preview("[verb-forms LLM]", text)
    elif parts:
        _stream_finalize_line()
    if finish_reason == "length":
        log_warn(
            "[llm] finish_reason=length — вывод обрезан сервером (часто внутренний n_predict < запроса max_tokens). "
            "Снизить VERB_FORMS_SCOPES_PER_REQUEST (например 2) или поднять -n / --ctx-size на llama-server."
        )
    return text, finish_reason


def _openai_chat_blocking(
    api_url: str,
    api_model: str,
    messages: List[dict],
    api_key: str,
    temperature: float,
    lemma: str,
    max_tokens: int,
    timeout: int = 600,
) -> Tuple[str, Optional[str]]:
    """Запасной вариант без stream, если сервер не отдал SSE. (text, finish_reason)."""
    chat_url = api_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": api_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if str(api_key or "").strip():
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        chat_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    log_warn(f"[llm] fallback POST stream=0 lemma={lemma}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    ch0 = body["choices"][0]
    msg = ch0.get("message") or {}
    text = msg.get("content") or ""
    fr = ch0.get("finish_reason")
    return text, fr


def _llm_single_completion(
    lemma: str,
    api_url: str,
    api_model: str,
    api_key: str,
    max_tokens: int,
    messages: List[dict],
    batch_label: str,
    expected_card_count: int,
) -> List[dict]:
    """Один вызов chat/completions → JSON-массив карточек."""
    disable_stream = _verb_forms_disable_stream()
    content = ""
    finish_reason: Optional[str] = None

    def _do_blocking(reason: str) -> Tuple[str, Optional[str]]:
        log_warn(f"[llm] blocking: {reason}")
        text, fr = _openai_chat_blocking(
            api_url,
            api_model,
            messages,
            api_key,
            temperature=0.2,
            lemma=lemma,
            max_tokens=max_tokens,
        )
        _emit_blocking_preview("[verb-forms LLM]", text)
        return text, fr

    if disable_stream:
        log_info(
            f"[llm] {batch_label} VERB_FORMS_DISABLE_STREAM=1 → только blocking "
            f"{api_url.rstrip('/')}/chat/completions lemma={lemma} max_tokens={max_tokens}"
        )
        content, finish_reason = _do_blocking("режим без SSE по env")
    else:
        log_info(
            f"[llm] {batch_label} stream=1 {api_url.rstrip('/')}/chat/completions "
            f"lemma={lemma} model={api_model} max_tokens={max_tokens}"
        )
        try:
            content, finish_reason = _openai_chat_stream(
                api_url,
                api_model,
                messages,
                api_key,
                temperature=0.2,
                lemma=lemma,
                max_tokens=max_tokens,
            )
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            content, finish_reason = _do_blocking(f"stream failed ({e})")

    if not (content or "").strip():
        content, finish_reason = _do_blocking("stream вернул пустой текст")

    if not (content or "").strip():
        log_warn("[llm] blocking пустой — пауза 3s и повтор blocking (иногда сервер даёт сбой после обрезки)")
        time.sleep(3)
        content, finish_reason = _do_blocking("повтор после паузы")

    if not (content or "").strip():
        raise RuntimeError(
            "LLM вернул пустой ответ (stream+blocking×2). Попробуй VERB_FORMS_DISABLE_STREAM=1 или поднять -n на llama-server."
        )
    log_ok(f"[llm] приём завершён {batch_label} lemma={lemma} chars={len(content)}")
    scopes_in_batch = max(1, expected_card_count // 6)

    def _raise_trunc_split(msg: str) -> None:
        if scopes_in_batch > 1:
            raise OutputTruncatedError(msg)
        raise RuntimeError(
            msg + " Один scope не помещается — подними -n на llama-server или VERB_FORMS_DISABLE_STREAM=1."
        )

    min_chars = _expected_json_min_chars(expected_card_count)
    if finish_reason == "length" and len(content.strip()) < min_chars and scopes_in_batch > 1:
        log_info(
            f"[llm] finish_reason=length и ответ короткий ({len(content)} < ~{min_chars} симв для {expected_card_count} карточек) — дробим батч без парсинга"
        )
        _raise_trunc_split("response too short after length")

    try:
        parsed = parse_llm_json(content)
        if not isinstance(parsed, list):
            raise ValueError("LLM ответ не JSON-массив")
    except JSONDecodeError as e:
        if finish_reason == "length" and scopes_in_batch > 1:
            log_info(f"[llm] JSON битый при finish_reason=length — дробим батч ({scopes_in_batch} scope), без повтора полного запроса")
            _raise_trunc_split("JSON incomplete after length truncation")
        _log_json_decode_failure(lemma, content, e)
        raise

    if finish_reason == "length" and len(parsed) < expected_card_count:
        if scopes_in_batch > 1:
            log_info(
                f"[llm] при length не хватает карточек: {len(parsed)}/{expected_card_count} — дробим батч"
            )
            _raise_trunc_split("fewer cards than expected after length truncation")
        raise RuntimeError(
            f"ожидалось {expected_card_count} карточек, получено {len(parsed)}; подними лимит генерации на llama-server"
        )
    return parsed


def _fetch_scope_batch_recursive(
    lemma: str,
    api_url: str,
    api_model: str,
    api_key: str,
    max_tokens: int,
    system_tpl: str,
    compact_system_tpl: str,
    scopes_batch: List[str],
    bi: int,
    total_b: int,
    split_depth: int,
) -> List[dict]:
    """
    Один HTTP-запрос на набор scope; при ошибке парсинга/пустого ответа — повторы того же батча,
    затем дробление списка scope пополам (2+2, 1+1, …) без повторного запроса уже принятых батчей.
    """
    if not scopes_batch:
        return []
    attempts = _batch_inline_retries()
    last_err: Optional[Exception] = None
    trunc_split = False
    for att in range(1, attempts + 1):
        tpl = compact_system_tpl if (split_depth >= 1 or att >= 2) else system_tpl
        messages = _build_batch_messages(lemma, tpl, scopes_batch, bi, total_b)
        label = _batch_label(bi, total_b, scopes_batch, split_depth)
        if att > 1:
            log_warn(f"[batch retry] {label} попытка {att}/{attempts} (тот же набор scope)")
        try:
            return _llm_single_completion(
                lemma,
                api_url,
                api_model,
                api_key,
                max_tokens,
                messages,
                label,
                expected_card_count=6 * len(scopes_batch),
            )
        except OutputTruncatedError:
            trunc_split = True
            log_info(
                f"[batch split] обрезка ответа (length) — делим {len(scopes_batch)} scope без лишних полных ретраев"
            )
            break
        except Exception as e:
            last_err = e
            if att < attempts:
                log_warn(f"[batch retry] {label} ошибка: {short_text(str(e), 200)}")
    if len(scopes_batch) <= 1:
        if last_err is not None:
            raise last_err
        raise RuntimeError("empty scope batch")
    mid = len(scopes_batch) // 2
    left, right = scopes_batch[:mid], scopes_batch[mid:]
    if trunc_split:
        log_warn(
            f"[batch split] {_batch_label(bi, total_b, scopes_batch, split_depth)} → "
            f"{len(left)}+{len(right)} scope (finish_reason=length / неполный JSON)"
        )
    else:
        log_warn(
            f"[batch split] {_batch_label(bi, total_b, scopes_batch, split_depth)} → "
            f"{len(left)}+{len(right)} scope после {attempts} неудач: {short_text(str(last_err), 200)}"
        )
    a = _fetch_scope_batch_recursive(
        lemma,
        api_url,
        api_model,
        api_key,
        max_tokens,
        system_tpl,
        compact_system_tpl,
        left,
        bi,
        total_b,
        split_depth + 1,
    )
    b = _fetch_scope_batch_recursive(
        lemma,
        api_url,
        api_model,
        api_key,
        max_tokens,
        system_tpl,
        compact_system_tpl,
        right,
        bi,
        total_b,
        split_depth + 1,
    )
    return a + b


def llm_generate_cards(
    lemma: str,
    api_url: str,
    api_model: str,
    api_key: str,
    *,
    chunk_validate_retries: int,
) -> List[dict]:
    """
    Полное покрытие 16×6 карточек. Локальный llama-server часто режет длинный JSON (finish_reason=length),
    по умолчанию VERB_FORMS_SCOPES_PER_REQUEST=4 (4 HTTP-запроса на лемму). Для слабого/резкого ctx: поставьте =2 (8 запросов).
    При finish_reason=length — сразу дробление батча без лишних полных ретраев. Иначе: VERB_FORMS_BATCH_PARSE_RETRIES, затем split.

    После каждого HTTP-чанка вызывается validate_cards_for_scopes; при ошибке перегенерируется только этот чанк
    (до chunk_validate_retries раз), без повтора уже принятых частей леммы.

    Env для нестабильного llama-server / пустого SSE после обрезки:
    VERB_FORMS_DISABLE_STREAM=1 — только blocking (часто стабильнее stream после length).

    Автозапуск локального сервера (если не отвечает): см. модульный docstring и ensure_llamacpp_for_verb_forms().
    """
    per = _scopes_per_llm_request()
    batches = _chunk_scopes(EXPECTED_SCOPES, per)
    max_tokens = _max_output_tokens()
    all_cards: List[dict] = []

    system_tpl = (
        "Ты генерируешь JSON-данные тренировки испанских глаголов.\n"
        "В ЭТОМ ответе нужны ТОЛЬКО перечисленные в expected_scopes времена (scopes).\n"
        "Для КАЖДОГО scope — ровно 6 форм (все лица из expected_slots).\n"
        "Поля каждой формы: scope, mood, tense, person, number, surface_form, question_es_with_blank, translation_ru_full, options.\n"
        "options: ровно 4 варианта, один из них surface_form.\n"
        "Внутри одного scope пары (question_es_with_blank + translation_ru_full) должны быть уникальными.\n\n"
        "Качество языка (обязательно проверь до вывода JSON):\n"
        "- Испанский: surface_form должна быть именно той грамматической формой, которая соответствует scope + person + number "
        "(правильное спряжение, правильное время и наклонение). Предложение в question_es_with_blank должно быть естественным "
        "на испанском; на месте пропуска подставляется только правильная surface_form.\n"
        "- Русский (translation_ru_full): грамотная фраза целиком — согласование по лицу/числу/роду где нужно, правильные окончания "
        "глаголов и не только; время и модальность перевода должны соответствовать смыслу испанского времени в этом scope "
        "(настоящее/прошлое/условное/сослагательное и т.д.). Избегай кальки и фраз, которые звучат по-русски неправильно; "
        "если сомневаешься — выбери более естественный русский эквивалент при сохранении времени.\n"
        "- Неверные формы в distractors (options): только реалистичные ошибки ученика (близкие окончания/не то время), без случайного мусора.\n\n"
        "Ответ только валидный JSON-массив, без markdown. Строго двойные кавычки в JSON, без хвостовых запятых.\n"
        "Внутри JSON-строк не делай сырых переносов строк; переводы — короткие в одну фразу.\n"
        "Не обрывай JSON посередине ключа или значения: при нехватке места сокращай translation_ru_full, но оставь массив закрытым и валидным."
    )

    compact_system_tpl = (
        "Верни только JSON-массив для испанского глагола (лемма в user JSON).\n"
        "Только expected_scopes из запроса; на каждый scope ровно 6 объектов по expected_slots.\n"
        "Поля объекта: scope, mood, tense, person, number, surface_form, question_es_with_blank, translation_ru_full, "
        "options как массив из 4 строк (одна совпадает с surface_form).\n"
        "translation_ru_full — минимально короткая грамотная русская фраза (цель до ~60 символов), без кальки.\n"
        "Без markdown, только валидный JSON; без переносов внутри строк; без хвостовых запятых.\n"
        "Обрежь русский текст раньше, чем оборвёшь скобки массива."
    )

    total_b = len(batches)
    log_info(
        f"[llm] lemma={lemma}: {total_b} запрос(ов) по {per} scope (VERB_FORMS_SCOPES_PER_REQUEST), "
        f"max_tokens={max_tokens}"
    )

    for bi, scopes_batch in enumerate(batches, start=1):
        if _PROGRESS is not None:
            _PROGRESS.set_chunk(f"batch {bi}/{total_b}", 0, 0)
        label_base = _batch_label(bi, total_b, scopes_batch, 0)
        chunk_cards: Optional[List[dict]] = None
        last_chunk_err: Optional[Exception] = None
        for catt in range(1, chunk_validate_retries + 1):
            try:
                if catt > 1:
                    log_warn(
                        f"[chunk validate retry] lemma={lemma} {label_base} попытка {catt}/{chunk_validate_retries}"
                    )
                chunk_cards = _fetch_scope_batch_recursive(
                    lemma,
                    api_url,
                    api_model,
                    api_key,
                    max_tokens,
                    system_tpl,
                    compact_system_tpl,
                    scopes_batch,
                    bi,
                    total_b,
                    split_depth=0,
                )
                validate_cards_for_scopes(chunk_cards, scopes_batch)
                if catt > 1:
                    log_ok(f"[chunk validate] lemma={lemma} {label_base} OK после {catt} попыток")
                break
            except Exception as e:
                last_chunk_err = e
                if catt < chunk_validate_retries:
                    log_warn(
                        f"[chunk validate] lemma={lemma} {label_base} попытка {catt}/{chunk_validate_retries}: "
                        f"{short_text(str(e), 220)}"
                    )
                else:
                    raise RuntimeError(
                        f"chunk validation failed after {chunk_validate_retries} attempt(s) for {label_base}: "
                        f"{last_chunk_err}"
                    ) from last_chunk_err
        assert chunk_cards is not None
        all_cards.extend(chunk_cards)

    return all_cards


def _llamacpp_http_base_from_env() -> str:
    """Базовый URL без суффикса /v1 — для GET /v1/models и /health."""
    raw = os.environ.get("LLAMACPP_URL", os.environ.get("AI_URL", "")).strip().rstrip("/")
    if not raw:
        return ""
    if raw.endswith("/v1"):
        raw = raw[:-3].rstrip("/")
    return raw


def _llamacpp_probe_ready(http_base: str) -> bool:
    if not http_base:
        return False
    base = http_base.rstrip("/")
    for path in ("/v1/models", "/health"):
        url = base + path
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except (OSError, urllib.error.URLError, urllib.error.HTTPError):
            continue
    return False


def ensure_llamacpp_for_verb_forms() -> None:
    """Если нужно — выполнить LLAMACPP_START_CMD_* и дождаться ответа llama/OpenAI-compat сервера."""
    mode = os.environ.get("VERB_FORMS_ENSURE_LLAMA", "auto").strip().lower()
    if mode in ("0", "false", "no", "off"):
        return

    http_base = _llamacpp_http_base_from_env()
    start_cmd = (
        os.environ.get("LLAMACPP_START_CMD_VERB", "").strip()
        or os.environ.get("LLAMACPP_START_CMD", "").strip()
    )

    wait_raw = os.environ.get("LLAMACPP_START_MAX_WAIT_SEC", "").strip()
    try:
        max_wait = int(wait_raw) if wait_raw else 120
    except ValueError:
        max_wait = 120
    max_wait = max(5, min(max_wait, 3600))

    if mode == "auto" and not start_cmd:
        return

    if _llamacpp_probe_ready(http_base):
        log_ok("[llama] сервер уже доступен")
        return

    if not start_cmd:
        log_warn(
            "[llama] сервер не отвечает и команда автозапуска не задана "
            "(LLAMACPP_START_CMD или LLAMACPP_START_CMD_VERB); продолжаем"
        )
        return

    log_info("[llama] автозапуск (START_CMD)...")
    subprocess.run(["bash", "-lc", start_cmd], check=False)

    for i in range(max_wait):
        if _llamacpp_probe_ready(http_base):
            log_ok(f"[llama] готов через {i + 1}s")
            return
        time.sleep(1)

    log_warn(
        f"[llama] не поднялся за {max_wait}s — проверьте порт и флаги (-n не ниже VERB_FORMS_MAX_TOKENS)"
    )


def load_env_file(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    global _PROGRESS
    parser = argparse.ArgumentParser(description="Generate Spanish verb forms training artifacts via LLM.")
    parser.add_argument("--course-root", default=".", help="Path to course root (default: .)")
    parser.add_argument("--limit", type=int, default=100, help="Pending API page size")
    parser.add_argument("--max-retries", type=int, default=3, help="LLM retries per lemma (полная перегенерация)")
    parser.add_argument(
        "--chunk-validate-retries",
        type=int,
        default=None,
        help="Попыток на один HTTP-чанк при ошибке семантической валидации "
        "(env VERB_FORMS_CHUNK_VALIDATE_RETRIES, по умолчанию 8). Перегенерируется только этот чанк.",
    )
    parser.add_argument(
        "--all-verbs",
        action="store_true",
        help="Use pending API with all=1: every infinitive-like verb headword (verb POS card), "
        "not only lemmas missing verb_forms_dict. Needed after full DB sync when gap list is empty.",
    )
    parser.add_argument(
        "--all-verbs-on-empty",
        action="store_true",
        help="If first pending page is empty (gap mode), retry from cursor 0 with --all-verbs behavior.",
    )
    args = parser.parse_args()
    chunk_validate_retries = _chunk_validation_retries(args.chunk_validate_retries)
    _PROGRESS = ProgressLine()

    course_root = Path(args.course_root).resolve()
    pack_root = course_root / "training_pack" / "verb_forms"
    lemmas_dir = pack_root / "lemmas"
    index_path = pack_root / "index.json"

    load_env_file(course_root.parent.parent / ".env")
    load_env_file(course_root.parent.parent / ".env.es")
    load_env_file(course_root / ".env.local")

    ensure_llamacpp_for_verb_forms()

    server_port = str(os.environ.get("SERVER_PORT", "8184")).strip() or "8184"
    local_api_default = f"http://127.0.0.1:{server_port}"
    internal_api = os.environ.get(
        "VERB_TRAINING_INTERNAL_API",
        os.environ.get(
            "COMPLAINTS_SERVICE_URL",
            os.environ.get("WEBAPP_PUBLIC_URL", local_api_default),
        ),
    ).rstrip("/")
    service_token = os.environ.get("WEBAPP_INTERNAL_SERVICE_TOKEN", os.environ.get("COMPLAINTS_SERVICE_TOKEN", ""))
    # Как в tools-local/complaints-worker/*: локальный llama-server — основной источник.
    # AI_URL/AI_MODEL — только fallback (например CI или облачный провайдер).
    llm_url = os.environ.get("LLAMACPP_URL", os.environ.get("AI_URL", "")).rstrip("/")
    llm_model = os.environ.get("LLAMACPP_MODEL", os.environ.get("AI_MODEL", ""))
    llm_key = os.environ.get("AI_API_KEY", "").strip()
    if llm_url and not llm_url.rstrip("/").endswith("/v1"):
        llm_url = llm_url.rstrip("/") + "/v1"

    if not service_token:
        print("WEBAPP_INTERNAL_SERVICE_TOKEN (or COMPLAINTS_SERVICE_TOKEN) is required", file=sys.stderr)
        return 2
    if not llm_url or not llm_model:
        print(
            "LLAMACPP_URL + LLAMACPP_MODEL required (или fallback AI_URL + AI_MODEL); для llama.cpp ключ не нужен.",
            file=sys.stderr,
        )
        return 2

    log_ok(f"{ANSI_BOLD}verb_forms generation started{ANSI_RESET}")
    log_info(f"internal_api={internal_api}")
    llm_src = "LLAMACPP_*" if os.environ.get("LLAMACPP_URL") else "AI_* fallback"
    log_info(f"llm_url={llm_url} model={llm_model} (env source: {llm_src})")
    log_info(f"course_root={course_root}")
    log_info(f"chunk_validate_retries={chunk_validate_retries} (per HTTP chunk; env VERB_FORMS_CHUNK_VALIDATE_RETRIES / --chunk-validate-retries)")

    if index_path.exists():
        index = read_json(index_path)
    else:
        index = {
            "version": "v1",
            "language": "es",
            "generated_at": "",
            "generator": {"name": "generate-verb-forms-training.py", "model": llm_model},
            "generation_coverage": {
                "required_scopes": EXPECTED_SCOPES,
                "required_slots_per_scope": [f"{p}:{n}" for p, n in EXPECTED_SLOTS],
            },
            "lemmas": {},
        }
    index.setdefault("lemmas", {})
    cursor = 0
    processed = 0
    use_all_verbs = bool(args.all_verbs)
    retried_all_verbs = False
    while True:
        try:
            data = fetch_pending(internal_api, service_token, args.limit, cursor, all_verbs=use_all_verbs)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 1
        items = data.get("items", [])
        _PROGRESS.set_total_hint(int(data.get("count", 0) or 0))
        if (
            not items
            and cursor == 0
            and not use_all_verbs
            and args.all_verbs_on_empty
            and not retried_all_verbs
        ):
            log_warn(
                "[pending] count=0 in gap mode — DB likely already has verb_forms for these lemmas. "
                "Retrying with all=1 (infinitives with verb training_cards)."
            )
            use_all_verbs = True
            retried_all_verbs = True
            continue
        if not items:
            if cursor == 0 and not use_all_verbs:
                log_warn(
                    "[pending] nothing to do. For pack-fill against a synced DB, run with "
                    "`--all-verbs-on-empty` or `--all-verbs` (see generate-verb-forms-training.py --help)."
                )
            break
        batch_lemmas = [normalize_text(it.get("lemma")) for it in items if normalize_text(it.get("lemma"))]
        if batch_lemmas:
            log_ok(
                f"[pending] батч: {len(batch_lemmas)} глагол(ов) для генерации: "
                f"{', '.join(batch_lemmas)}"
            )
        for item in items:
            lemma = normalize_text(item.get("lemma"))
            if not lemma:
                continue
            _PROGRESS.set_current_lemma(lemma)
            target_file = lemmas_dir / f"{lemma}.json"
            if target_file.exists():
                log_warn(f"[skip] lemma={lemma} file already exists")
                continue
            log_info(f"[generate] lemma={lemma}")
            last_error = None
            cards = None
            for attempt in range(1, args.max_retries + 1):
                try:
                    _PROGRESS.set_chunk("lemma generation", attempt, args.max_retries)
                    log_info(f"[llm] attempt={attempt}/{args.max_retries} lemma={lemma}")
                    cards = llm_generate_cards(
                        lemma,
                        llm_url,
                        llm_model,
                        llm_key,
                        chunk_validate_retries=chunk_validate_retries,
                    )
                    validate_artifact(lemma, cards)
                    log_ok(f"[validate] lemma={lemma} strict coverage OK")
                    break
                except Exception as e:
                    last_error = e
                    cards = None
                    log_warn(f"[retry] lemma={lemma} attempt={attempt} error={short_text(e)}")
            if cards is None:
                log_err(f"[failed] lemma={lemma}: {short_text(last_error)}")
                _PROGRESS.clear_chunk()
                continue
            artifact = {
                "version": "v1",
                "language": "es",
                "lemma": lemma,
                "generated_at": utc_now(),
                "cards": [normalize_card(c) for c in cards],
            }
            validate_artifact(lemma, artifact["cards"])
            write_json(target_file, artifact)
            index["lemmas"][lemma] = f"lemmas/{lemma}.json"
            # Persist index incrementally so Ctrl+C does not lose already generated lemmas in admin/tools.
            index["generated_at"] = utc_now()
            index["generator"] = {"name": "generate-verb-forms-training.py", "model": llm_model}
            write_json(index_path, index)
            processed += 1
            _PROGRESS.set_processed(processed)
            _PROGRESS.clear_chunk()
            log_ok(f"[saved] lemma={lemma} cards={len(artifact['cards'])} file={target_file.name}")
        cursor = int(data.get("next_cursor", 0))
        if cursor <= 0:
            break

    index["generated_at"] = utc_now()
    index["generator"] = {"name": "generate-verb-forms-training.py", "model": llm_model}
    write_json(index_path, index)
    _PROGRESS.finalize()
    log_ok(f"{ANSI_BOLD}done{ANSI_RESET}, processed={processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

