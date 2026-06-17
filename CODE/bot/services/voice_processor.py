"""
voice_processor.py — Транскрипция голоса (только русский)
"""
import os, tempfile
from pydub import AudioSegment
from bot.services.ai import client

CHUNK_MS = 10 * 60 * 1000

# Ключевые слова для режимов
MEETING_KEYWORDS = [
    "bayonnoma","sobraniye","собрание","yig'ilish","meeting",
    "протокол","шаблон собрания","kunlik uchrashuv","daily meeting","agenda","повестка"
]
SUMMARY_KEYWORDS = [
    "резюме","краткое","summary","qisqacha","главные мысли","итоги","выдели"
]
FINANCE_KEYWORDS = [
    "финанс","деньги","расход","доход","бюджет","трата","moliya","pul","xarajat"
]

def detect_mode(text: str) -> str:
    t = text.lower()
    if any(kw in t for kw in MEETING_KEYWORDS): return "meeting"
    if any(kw in t for kw in SUMMARY_KEYWORDS): return "summary"
    if any(kw in t for kw in FINANCE_KEYWORDS): return "finance"
    return "chat"

def _normalize_audio(src_path: str) -> AudioSegment:
    """Моно 16 кГц — оптимально для Whisper, чинит битые метаданные."""
    return AudioSegment.from_file(src_path).set_channels(1).set_frame_rate(16000)

def _clean_hallucination(text: str) -> str:
    """Убирает повторяющиеся фразы-галлюцинации."""
    if not text:
        return ""
    sentences = [s.strip() for s in text.replace("\n"," ").split(".") if s.strip()]
    cleaned, prev, repeat = [], None, 0
    for s in sentences:
        if s == prev:
            repeat += 1
            if repeat >= 2: continue
        else:
            repeat = 0
        cleaned.append(s)
        prev = s
    return ". ".join(cleaned).strip()

def _transcribe_one(audio: AudioSegment) -> str:
    """
    Транскрибирует сегмент (только русский).
    """
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        audio.export(tmp_path, format="mp3", bitrate="64k")
        if audio.dBFS == float("-inf") or audio.dBFS < -50:
            return ""

        # Whisper с принудительным русским языком
        kwargs = dict(
            model="whisper-1",
            language="ru",
            temperature=0,
            response_format="text",
        )
        with open(tmp_path, "rb") as f:
            r = client.audio.transcriptions.create(file=f, **kwargs)
        text = r if isinstance(r, str) else getattr(r, "text", "")
        return _clean_hallucination(text.strip())

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def transcribe_audio(src_path: str) -> str:
    """Транскрибирует файл. Длинные — режет на 10-минутные куски."""
    audio = _normalize_audio(src_path)
    total_ms = len(audio)
    if total_ms <= CHUNK_MS:
        return _transcribe_one(audio)
    parts = []
    start = 0
    while start < total_ms:
        end = min(start + CHUNK_MS, total_ms)
        t = _transcribe_one(audio[start:end])
        if t:
            parts.append(t)
        start = end
    return " ".join(parts)
