"""
voice_processor.py — Умная обработка голосовых сообщений
=========================================================

Возможности:
  - Высококачественная транскрипция (рус + узб) через Whisper
  - Длинные записи (50-60 мин): разбивка на части по 24 МБ
  - Умный контекст: бот понимает что делать с аудио
  - Если контекст не указан — задаёт вопрос пользователю
  - Режимы: обычный диалог | резюме | собрание (Bayonnoma/Agenda)
"""

import io
import math
import os
import tempfile
from pathlib import Path

from pydub import AudioSegment

from bot import config
from bot.services.ai import client

# Максимальный размер одного куска для Whisper API — 24 МБ (лимит 25 МБ)
WHISPER_MAX_BYTES = 24 * 1024 * 1024

# Ключевые слова для определения режима из текста транскрипции или команды
MEETING_KEYWORDS = [
    "bayonnoma", "bayonnoma qil", "sobraniye", "собрание", "йиғилиш",
    "meeting", "протокол", "шаблон собрания", "шаблон1", "kunlik uchrashuv",
    "daily meeting", "резюме собрания"
]

SUMMARY_KEYWORDS = [
    "резюме", "краткое содержание", "summary", "qisqacha", "главные мысли",
    "что важное", "итоги", "выдели главное"
]

FINANCE_KEYWORDS = [
    "финанс", "деньги", "расход", "доход", "финансы", "бюджет", "трата",
    "moliya", "pul", "xarajat", "daromad"
]


def detect_mode(text: str) -> str:
    """
    Определяет режим обработки по тексту.
    Возвращает: 'meeting' | 'summary' | 'finance' | 'chat'
    """
    t = text.lower()
    if any(kw in t for kw in MEETING_KEYWORDS):
        return "meeting"
    if any(kw in t for kw in SUMMARY_KEYWORDS):
        return "summary"
    if any(kw in t for kw in FINANCE_KEYWORDS):
        return "finance"
    return "chat"


def transcribe_audio(ogg_path: str) -> str:
    """
    Транскрибирует аудио файл в текст.
    Длинные файлы разбивает на части по 24 МБ и склеивает результат.
    Использует промпт для лучшего качества на рус/узб.
    """
    file_size = os.path.getsize(ogg_path)

    # Загружаем аудио
    audio = AudioSegment.from_file(ogg_path)

    if file_size <= WHISPER_MAX_BYTES:
        # Короткое аудио — транскрибируем целиком
        return _transcribe_segment(audio, ogg_path)

    # Длинное аудио — разбиваем на части
    # Считаем продолжительность одной части пропорционально размеру
    total_ms = len(audio)
    parts_count = math.ceil(file_size / WHISPER_MAX_BYTES)
    part_ms = total_ms // parts_count

    transcripts = []
    for i in range(parts_count):
        start = i * part_ms
        end = min((i + 1) * part_ms, total_ms)
        segment = audio[start:end]
        part_text = _transcribe_segment(segment)
        transcripts.append(part_text)

    return " ".join(transcripts)


def _transcribe_segment(audio_or_path, path_hint=None) -> str:
    """Транскрибирует один сегмент аудио через Whisper."""
    prompt = (
        "Это личная заметка или запись разговора на русском или узбекском языке. "
        "Транскрибируй точно, сохраняя имена, термины и числа."
    )

    if isinstance(audio_or_path, str):
        # Это путь к файлу
        with open(audio_or_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                prompt=prompt,
            )
        return result.text
    else:
        # Это AudioSegment — экспортируем во временный файл
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            audio_or_path.export(tmp_path, format="mp3")
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    prompt=prompt,
                )
            return result.text
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
