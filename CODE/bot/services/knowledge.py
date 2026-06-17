"""
knowledge.py — База знаний Сенсея (Этап 15)
=============================================

Полноценная система хранения и структурирования знаний:
  - Ингест YouTube (субтитры → краткое содержание → оценка полезности)
  - Ручные заметки: «запомни: ...»
  - Поиск по базе знаний
  - Категоризация по сферам и тегам
  - Obsidian-совместимый экспорт

Команды:
  /learn <YouTube URL>   — загрузить видео в базу знаний
  /knowledge             — показать сохранённые знания
  /search <запрос>       — поиск по базе знаний

Текстовый ввод:
  «запомни: ...»         — сохранить заметку
  «что я знаю про ...»  — поиск по базе
"""

import json
import re
from datetime import datetime, date

from bot.database import db
from bot.services.ai import client


# ──────────────────────────────────────────────────
# Инициализация таблицы
# ──────────────────────────────────────────────────
def init_knowledge_table():
    db.cursor.execute("""
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        type TEXT,         -- 'youtube' | 'note' | 'book' | 'article' | 'insight'
        title TEXT,        -- название/заголовок
        source TEXT,       -- URL или "manual"
        summary TEXT,      -- краткое содержание
        key_points TEXT,   -- ключевые мысли (JSON array)
        relevance TEXT,    -- оценка полезности для целей (JSON: {sphere: score})
        tags TEXT,         -- теги через запятую
        sphere TEXT,       -- основная сфера: youtube/services/pulinform/life/general
        raw_content TEXT,  -- полный текст (для поиска)
        created_at TEXT
    )
    """)
    db.conn.commit()


init_knowledge_table()


# ──────────────────────────────────────────────────
# YouTube ингест
# ──────────────────────────────────────────────────
def _get_youtube_transcript(url: str) -> str | None:
    """Получает транскрипт YouTube видео через youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        # Извлекаем video_id из URL
        video_id = None
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break

        if not video_id:
            return None

        # Пробуем получить субтитры (русские → английские → авто)
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                transcript = transcript_list.find_transcript(['ru', 'en'])
            except Exception:
                transcript = transcript_list.find_generated_transcript(['ru', 'en'])
            
            entries = transcript.fetch()
            text = " ".join([entry.text for entry in entries])
            return text[:15000]  # Ограничиваем длину для GPT
        except Exception:
            return None

    except ImportError:
        return None
    except Exception:
        return None


def _get_youtube_title(url: str) -> str:
    """Получает заголовок YouTube видео."""
    try:
        import urllib.request
        video_id = None
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break
        if not video_id:
            return "Видео"
        
        # Простой способ через oembed
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("title", "Видео")
    except Exception:
        return "Видео"


def ingest_youtube(user_id, url: str) -> str:
    """Загружает YouTube видео в базу знаний."""
    # 1. Получаем транскрипт
    transcript = _get_youtube_transcript(url)
    if not transcript:
        return ("⚠️ Не удалось получить субтитры этого видео.\n"
                "Возможные причины: нет субтитров, приватное видео, или модуль не установлен.\n"
                "Попробуй: скопируй текст из видео вручную и отправь с «запомни: ...»")

    title = _get_youtube_title(url)

    # 2. Анализируем через GPT
    analysis = _analyze_content(user_id, transcript, title, "youtube", url)
    if not analysis:
        return "⚠️ Ошибка анализа видео."

    # 3. Сохраняем
    _save_knowledge(user_id, analysis, url)

    # 4. Формируем ответ
    relevance = analysis.get("relevance", {})
    rel_lines = []
    for sphere, score in relevance.items():
        if score >= 7:
            rel_lines.append(f"  🟢 {sphere}: {score}/10")
        elif score >= 4:
            rel_lines.append(f"  🟡 {sphere}: {score}/10")
        else:
            rel_lines.append(f"  ⚪ {sphere}: {score}/10")

    return (
        f"📚 *Знание сохранено!*\n\n"
        f"🎬 *{analysis.get('title', title)}*\n\n"
        f"📝 *Суть:*\n{analysis.get('summary', '')}\n\n"
        f"💡 *Ключевые мысли:*\n" +
        "\n".join([f"• {p}" for p in analysis.get("key_points", [])[:5]]) +
        f"\n\n📊 *Полезность для целей:*\n" +
        "\n".join(rel_lines) +
        f"\n\n🏷️ Теги: {analysis.get('tags', '')}"
    )


# ──────────────────────────────────────────────────
# Сохранение заметок
# ──────────────────────────────────────────────────
def save_note(user_id, text: str) -> str:
    """Сохраняет текстовую заметку в базу знаний."""
    # Убираем «запомни:» и подобное
    clean = re.sub(r'^(запомни|заметка|знание|сохрани)[:\s]*', '', text, flags=re.IGNORECASE).strip()
    if not clean:
        return "⚠️ Пустая заметка. Напиши что запомнить."

    analysis = _analyze_content(user_id, clean, "", "note", "manual")
    if not analysis:
        # Сохраняем без анализа
        _save_knowledge(user_id, {
            "type": "note",
            "title": clean[:50],
            "summary": clean,
            "key_points": [clean],
            "relevance": {},
            "tags": "",
            "sphere": "general",
        }, "manual")
        return f"📝 *Заметка сохранена:*\n{clean}"

    _save_knowledge(user_id, analysis, "manual")
    return (
        f"📝 *Знание сохранено!*\n\n"
        f"📌 *{analysis.get('title', clean[:50])}*\n"
        f"🏷️ {analysis.get('tags', '')}\n"
        f"🎯 Сфера: {analysis.get('sphere', 'general')}"
    )


# ──────────────────────────────────────────────────
# Поиск по базе знаний
# ──────────────────────────────────────────────────
def search_knowledge(user_id, query: str) -> str:
    """Ищет по базе знаний."""
    # Простой поиск LIKE
    search_term = f"%{query}%"
    db.cursor.execute("""
    SELECT id, title, summary, type, sphere, created_at FROM knowledge
    WHERE user_id=? AND (
        title LIKE ? OR summary LIKE ? OR key_points LIKE ? OR tags LIKE ? OR raw_content LIKE ?
    )
    ORDER BY created_at DESC LIMIT 10
    """, (str(user_id), search_term, search_term, search_term, search_term, search_term))
    rows = db.cursor.fetchall()

    if not rows:
        return f"🔍 По запросу «{query}» ничего не найдено в базе знаний."

    lines = [f"🔍 *Найдено ({len(rows)}):*\n"]
    emoji_map = {"youtube": "🎬", "note": "📝", "book": "📖", "article": "📄", "insight": "💡"}
    for row in rows:
        id_, title, summary, k_type, sphere, created = row
        e = emoji_map.get(k_type, "📌")
        short_summary = (summary[:80] + "...") if summary and len(summary) > 80 else (summary or "")
        lines.append(f"{e} *{title}*\n   {short_summary}\n")

    return "\n".join(lines)


def list_knowledge(user_id, limit: int = 10) -> str:
    """Список последних записей в базе знаний."""
    db.cursor.execute("""
    SELECT id, title, type, sphere, created_at FROM knowledge
    WHERE user_id=?
    ORDER BY created_at DESC LIMIT ?
    """, (str(user_id), limit))
    rows = db.cursor.fetchall()

    if not rows:
        return ("📚 *База знаний пуста.*\n\n"
                "Добавь знания:\n"
                "• `/learn <YouTube URL>` — из видео\n"
                "• `запомни: ...` — текстовая заметка\n"
                "• `/search <запрос>` — поиск")

    # Считаем общее количество
    db.cursor.execute("SELECT COUNT(*) FROM knowledge WHERE user_id=?", (str(user_id),))
    total = db.cursor.fetchone()[0]

    emoji_map = {"youtube": "🎬", "note": "📝", "book": "📖", "article": "📄", "insight": "💡"}
    lines = [f"📚 *База знаний ({total} записей):*\n"]
    for row in rows:
        id_, title, k_type, sphere, created = row
        e = emoji_map.get(k_type, "📌")
        d = created[:10] if created else ""
        lines.append(f"{e} {title} [{sphere}] ({d})")

    lines.append(f"\n🔍 Поиск: `/search <запрос>`")
    return "\n".join(lines)


# ──────────────────────────────────────────────────
# Анализ контента через GPT
# ──────────────────────────────────────────────────
def _analyze_content(user_id, content: str, title: str, content_type: str, source: str) -> dict | None:
    """Анализирует контент и возвращает структурированные данные."""
    system_prompt = """Ты — аналитик знаний для личного ИИ-наставника Бекзода.

4 сферы владельца:
1. pulinform — работа по найму (взыскание долгов)
2. youtube — YouTube без лица (англоязычный рынок)
3. services — продажа сайтов/услуг локальному бизнесу США
4. life — жизнь, быт, здоровье, духовность

Главная цель: $30 000 от продажи услуг.

Проанализируй контент и верни ТОЛЬКО JSON:
{
  "type": "тип контента",
  "title": "краткий заголовок (до 60 символов)",
  "summary": "краткое содержание (3-5 предложений, максимум 200 слов)",
  "key_points": ["ключевая мысль 1", "ключевая мысль 2", "...", максимум 5],
  "relevance": {"youtube": 0-10, "services": 0-10, "pulinform": 0-10, "life": 0-10},
  "tags": "тег1, тег2, тег3",
  "sphere": "основная сфера (youtube/services/pulinform/life/general)"
}

Оценка relevance:
- 9-10: прямо применимо к цели прямо сейчас
- 6-8: полезно, применимо в ближайшее время
- 3-5: может пригодиться в будущем
- 0-2: не относится к этой сфере

Верни ТОЛЬКО JSON, без markdown."""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Тип: {content_type}\nЗаголовок: {title}\nИсточник: {source}\n\nКонтент:\n{content[:8000]}"},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        return None


# ──────────────────────────────────────────────────
# Сохранение в БД
# ──────────────────────────────────────────────────
def _save_knowledge(user_id, data: dict, source: str):
    """Сохраняет запись в таблицу knowledge."""
    now = datetime.now().isoformat()
    key_points = json.dumps(data.get("key_points", []), ensure_ascii=False)
    relevance = json.dumps(data.get("relevance", {}), ensure_ascii=False)

    db.cursor.execute("""
    INSERT INTO knowledge (user_id, type, title, source, summary, key_points, relevance, tags, sphere, raw_content, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(user_id),
        data.get("type", "note"),
        data.get("title", ""),
        source,
        data.get("summary", ""),
        key_points,
        relevance,
        data.get("tags", ""),
        data.get("sphere", "general"),
        data.get("summary", ""),  # raw_content = summary для заметок
        now,
    ))
    db.conn.commit()


# ──────────────────────────────────────────────────
# Obsidian-совместимый экспорт
# ──────────────────────────────────────────────────
def export_obsidian(user_id) -> str:
    """Экспортирует базу знаний в Obsidian-формат (один файл)."""
    db.cursor.execute("""
    SELECT title, type, source, summary, key_points, tags, sphere, created_at
    FROM knowledge WHERE user_id=? ORDER BY created_at DESC
    """, (str(user_id),))
    rows = db.cursor.fetchall()

    if not rows:
        return "Нет записей для экспорта."

    lines = ["# 🧠 База знаний Сенсея\n"]
    lines.append(f"Экспорт: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"Записей: {len(rows)}\n\n---\n")

    for row in rows:
        title, k_type, source, summary, key_points_json, tags, sphere, created = row
        lines.append(f"## {title}")
        lines.append(f"- **Тип:** {k_type}")
        lines.append(f"- **Сфера:** {sphere}")
        lines.append(f"- **Теги:** {tags}")
        if source and source != "manual":
            lines.append(f"- **Источник:** {source}")
        lines.append(f"- **Дата:** {created[:10]}")
        lines.append(f"\n{summary}\n")
        try:
            points = json.loads(key_points_json) if key_points_json else []
            if points:
                lines.append("**Ключевые мысли:**")
                for p in points:
                    lines.append(f"- {p}")
        except Exception:
            pass
        lines.append("\n---\n")

    return "\n".join(lines)


# ──────────────────────────────────────────────────
# Главная функция (вызывается из smart_input)
# ──────────────────────────────────────────────────
def process_knowledge(user_id, text: str) -> str | None:
    """
    Обрабатывает знание-ввод. None если не про знания.
    Определяет: запомни/заметка/что я знаю/покажи знания.
    """
    t = text.lower().strip()

    # Сохранение заметки
    if re.match(r'^(запомни|заметка|сохрани в знания|знание)[:\s]', t):
        return save_note(user_id, text)

    # Поиск
    if re.match(r'^(что я знаю|поиск по знаниям|найди в знаниях|search)[:\s]', t):
        query = re.sub(r'^(что я знаю|поиск по знаниям|найди в знаниях|search)[:\s]*', '', t, flags=re.IGNORECASE).strip()
        if query:
            return search_knowledge(user_id, query)

    # Список
    if t in ("знания", "мои знания", "база знаний", "покажи знания", "knowledge"):
        return list_knowledge(user_id)

    return None
