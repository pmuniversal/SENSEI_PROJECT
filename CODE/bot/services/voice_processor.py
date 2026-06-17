"""
voice_processor.py — Транскрипция рус+узб с конвертацией в латиницу
"""
import os, re, tempfile
from pydub import AudioSegment
from bot.services.ai import client

CHUNK_MS = 10 * 60 * 1000

# Кириллица → узбекская латиница
_CYR_TO_LAT = {
    'А':'A','а':'a','Б':'B','б':'b','В':'V','в':'v','Г':'G','г':'g',
    'Д':'D','д':'d','Е':'E','е':'e','Ё':'Yo','ё':'yo','Ж':'J','ж':'j',
    'З':'Z','з':'z','И':'I','и':'i','Й':'Y','й':'y','К':'K','к':'k',
    'Л':'L','л':'l','М':'M','м':'m','Н':'N','н':'n','О':'O','о':'o',
    'П':'P','п':'p','Р':'R','р':'r','С':'S','с':'s','Т':'T','т':'t',
    'У':'U','у':'u','Ф':'F','ф':'f','Х':'X','х':'x','Ч':'Ch','ч':'ch',
    'Ш':'Sh','ш':'sh',"Ъ":"'","ъ":"'","Э":"E","э":"e","Ю":"Yu","ю":"yu",
    "Я":"Ya","я":"ya","Ц":"Ts","ц":"ts",
    'Ғ':"G'",'ғ':"g'",'Қ':'Q','қ':'q','Ҳ':'H','ҳ':'h',
    "Ў":"O'","ў":"o'",'Ң':'Ng','ң':'ng',
}

# Русские слова — оставляем кириллицей (частотные)
_RU_WORDS = {
    'да','нет','ничего','было','это','на','за','по','как','что','то',
    'я','ты','он','она','мы','они','вы','не','но','и','а','или',
    'было','будет','есть','нет','всё','всего','уже','ещё','так','вот',
}

def _is_russian_word(word: str) -> bool:
    w = word.lower().strip('.,!?;:')
    if w in _RU_WORDS:
        return True
    # Если слово содержит буквы которых нет в узбекском (Щ,Ь,Ц нечастые в узб)
    if re.search(r'[щьцъ]', w, re.IGNORECASE):
        return True
    return False

def _convert_to_latin(text: str) -> str:
    """Конвертирует узбекские слова из кириллицы в латиницу, русские оставляет."""
    words = text.split()
    result = []
    for word in words:
        if _is_russian_word(word):
            result.append(word)
        else:
            converted = ''.join(_CYR_TO_LAT.get(c, c) for c in word)
            result.append(converted)
    return ' '.join(result)

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
    Транскрибирует сегмент.
    Стратегия для рус+узб:
      1. Автоопределение языка (Whisper сам определяет узбекский/русский)
      2. Постобработка: кириллица → латиница для узбекских слов
      3. Temperature=0 для точности, prompt подсказывает контекст
    """
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        audio.export(tmp_path, format="mp3", bitrate="64k")
        if audio.dBFS == float("-inf") or audio.dBFS < -50:
            return ""

        # Вызов Whisper без явного language — автоопределение
        # Prompt помогает с узбекскими/русскими словами
        kwargs = dict(
            model="whisper-1",
            temperature=0,
            response_format="text",
            prompt="Uzbek va rus tilida. Узбекский и русский язык."
        )
        with open(tmp_path, "rb") as f:
            r = client.audio.transcriptions.create(file=f, **kwargs)
        text = r if isinstance(r, str) else getattr(r, "text", "")
        text = _clean_hallucination(text.strip())

        # Конвертация кириллицы → латиница для узбекских слов
        return _convert_to_latin(text)

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
