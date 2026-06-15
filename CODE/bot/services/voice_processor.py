"""
voice_processor.py — Умная обработка голосовых сообщений
=========================================================

Возможности:
  - Высококачественная транскрипция (рус + узб) через Whisper
  - Нормализация аудио (моно, 16 кГц) — чинит битые метаданные после сжатия
  - Длинные записи (50-60 мин): разбивка на части по ~10 минут
  - Умный контекст: бот понимает что делать с аудио
  - Защита от галлюцинаций Whisper (без инструктивного промпта)
"""

import os
import tempfile

from pydub import AudioSegment

from bot.services.ai import client

# Длина одного куска для Whisper — 10 минут (моно 16кГц mp3 ≈ 5-7 МБ, лимит 25 МБ)
CHUNK_MS = 10 * 60 * 1000  # 10 минут в миллисекундах

# Ключевые слова для определения режима
MEETING_KEYWORDS = [
    "bayonnoma", "sobraniye", "собрание", "йиғилиш", "yig'ilish",
    "meeting", "протокол", "шаблон собрания", "шаблон1", "kunlik uchrashuv",
    "daily meeting", "резюме собрания", "agenda", "повестка"
]
SUMMARY_KEYWORDS = [
    "резюме", "краткое содержание", "summary", "qisqacha", "главные мысли",
    "что важное", "итоги", "выдели главное", "краткое"
]
FINANCE_KEYWORDS = [
    "финанс", "деньги", "расход", "доход", "финансы", "бюджет", "трата",
    "moliya", "pul", "xarajat", "daromad"
]
CHAT_KEYWORDS = ["чат", "разговор", "chat", "обычный"]


def detect_mode(text: str) -> str:
    """Определяет режим: 'meeting' | 'summary' | 'finance' | 'chat'."""
    t = text.lower()
    if any(kw in t for kw in MEETING_KEYWORDS):
        return "meeting"
    if any(kw in t for kw in SUMMARY_KEYWORDS):
        return "summary"
    if any(kw in t for kw in FINANCE_KEYWORDS):
        return "finance"
    return "chat"


def _normalize_audio(src_path: str) -> AudioSegment:
    """
    Загружает аудио ЛЮБОГО формата и нормализует:
      - моно (1 канал)
      - 16 кГц (оптимально для распознавания речи)
    Это чинит битые метаданные после внешнего сжатия (m4a и т.д.).
    """
    audio = AudioSegment.from_file(src_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    return audio


def _transcribe_one(audio: AudioSegment) -> str:
    """Транскрибирует один сегмент. БЕЗ инструктивного промпта (избегаем галлюцинаций)."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        # Экспортируем с нормальным битрейтом
        audio.export(tmp_path, format="mp3", bitrate="64k")

        # Если сегмент почти тишина — пропускаем (защита от галлюцинаций)
        if audio.dBFS == float("-inf") or audio.dBFS < -50:
            return ""

        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                temperature=0,
                # НЕ передаём prompt с инструкциями! Это вызывало эхо-галлюцинации.
                # response_format text — чистый текст без таймкодов
                response_format="text",
            )
        # При response_format="text" возвращается строка
        text = result if isinstance(result, str) else getattr(result, "text", "")
        return _clean_hallucination(text)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _clean_hallucination(text: str) -> str:
    """
    Убирает повторяющиеся фразы-галлюцинации Whisper.
    Если одна и та же фраза повторяется подряд много раз — оставляем одну.
    """
    if not text:
        return ""
    # Разбиваем на предложения
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    cleaned = []
    prev = None
    repeat_count = 0
    for s in sentences:
        if s == prev:
            repeat_count += 1
            if repeat_count >= 2:  # больше 2 повторов подряд — пропускаем
                continue
        else:
            repeat_count = 0
        cleaned.append(s)
        prev = s
    return ". ".join(cleaned).strip()


def transcribe_audio(ogg_path: str) -> str:
    """
    Транскрибирует аудио файл в текст.
    Нормализует аудио, при необходимости режет на 10-минутные части.
    """
    audio = _normalize_audio(ogg_path)
    total_ms = len(audio)

    if total_ms <= CHUNK_MS:
        return _transcribe_one(audio)

    # Длинное аудио — режем на куски по 10 минут
    transcripts = []
    start = 0
    while start < total_ms:
        end = min(start + CHUNK_MS, total_ms)
        segment = audio[start:end]
        part_text = _transcribe_one(segment)
        if part_text:
            transcripts.append(part_text)
        start = end

    return " ".join(transcripts)
