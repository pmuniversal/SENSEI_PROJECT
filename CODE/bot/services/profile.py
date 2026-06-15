"""
profile.py — Долгая память: персональный профиль пользователя (Этап 7)
=======================================================================

Бот помнит не только 15 последних сообщений, а ЗНАЕТ пользователя:
- цели по сферам, ценности, привычки
- сильные/слабые стороны, паттерны поведения
- решения, инсайты, важные факты

После каждого разговора GPT извлекает ключевые факты и записывает в профиль.
При каждом ответе профиль подгружается в контекст.
"""

import json
from datetime import datetime

from bot.database import db
from bot.services.ai import client


# --------------------------------------------------
# Инициализация таблицы профиля
# --------------------------------------------------
def init_profile_table():
    """Создаёт таблицу profile если её нет."""
    db.cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        category TEXT,
        fact TEXT,
        source TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    db.conn.commit()


# Создаём таблицу при импорте модуля
init_profile_table()


# --------------------------------------------------
# Категории фактов
# --------------------------------------------------
CATEGORIES = [
    "goals",        # цели (по сферам)
    "strengths",    # сильные стороны
    "weaknesses",   # слабые стороны / зоны роста
    "patterns",     # паттерны поведения (прокрастинация, смена вектора и т.д.)
    "decisions",    # важные решения
    "values",       # ценности и убеждения
    "habits",       # привычки (хорошие и плохие)
    "projects",     # текущие проекты и их статус
    "insights",     # инсайты и важные мысли
    "personal",     # личные факты (семья, здоровье, контекст)
]


# --------------------------------------------------
# CRUD операции с профилем
# --------------------------------------------------
def get_profile(user_id) -> str:
    """
    Возвращает профиль пользователя как текст для подгрузки в системный промпт.
    Формат: по категориям, компактно.
    """
    db.cursor.execute(
        "SELECT category, fact FROM profile WHERE user_id=? ORDER BY category, id DESC",
        (str(user_id),)
    )
    rows = db.cursor.fetchall()

    if not rows:
        return ""

    # Группируем по категориям
    grouped = {}
    for category, fact in rows:
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(fact)

    # Форматируем
    category_names = {
        "goals": "🎯 Цели",
        "strengths": "💪 Сильные стороны",
        "weaknesses": "⚠️ Зоны роста",
        "patterns": "🔄 Паттерны поведения",
        "decisions": "✅ Решения",
        "values": "💎 Ценности",
        "habits": "🔁 Привычки",
        "projects": "📂 Проекты",
        "insights": "💡 Инсайты",
        "personal": "👤 Личное",
    }

    lines = ["=== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (долгая память) ==="]
    for cat, facts in grouped.items():
        name = category_names.get(cat, cat)
        lines.append(f"\n{name}:")
        for fact in facts[:10]:  # не более 10 фактов на категорию
            lines.append(f"  • {fact}")

    return "\n".join(lines)


def save_facts(user_id, facts: list):
    """
    Сохраняет список фактов в профиль.
    facts: [{"category": "goals", "fact": "Заработать $30000 на услугах"}]
    """
    now = str(datetime.now())
    for item in facts:
        cat = item.get("category", "insights")
        fact = item.get("fact", "")
        if not fact:
            continue

        # Проверяем дубликат (точное совпадение)
        db.cursor.execute(
            "SELECT id FROM profile WHERE user_id=? AND fact=?",
            (str(user_id), fact)
        )
        if db.cursor.fetchone():
            continue  # уже есть

        db.cursor.execute(
            """INSERT INTO profile (user_id, category, fact, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (str(user_id), cat, fact, "auto_extract", now, now)
        )

    db.conn.commit()


# --------------------------------------------------
# Автоматическое извлечение фактов из диалога
# --------------------------------------------------
def extract_facts_from_conversation(user_id, user_text: str, ai_text: str):
    """
    После каждого разговора GPT анализирует диалог и извлекает
    новые факты о пользователе для долгой памяти.
    Работает асинхронно (не блокирует ответ).
    """
    try:
        system_prompt = f"""Ты — модуль долгой памяти. Из диалога ниже извлеки НОВЫЕ факты 
о пользователе. Верни ТОЛЬКО JSON-массив (или пустой массив если ничего нового):

[{{"category": "goals|strengths|weaknesses|patterns|decisions|values|habits|projects|insights|personal", "fact": "краткий факт"}}]

Правила:
- Извлекай ТОЛЬКО конкретные факты (не общие рассуждения)
- Категории: goals (цели), strengths (сильные стороны), weaknesses (слабые/зоны роста),
  patterns (поведение), decisions (решения), values (ценности), habits (привычки),
  projects (проекты), insights (инсайты), personal (личное)
- Факт должен быть коротким (1-2 предложения)
- Если ничего нового — верни []
- НЕ дублируй то что очевидно или банально

Пользователь написал: {user_text}
AI ответил: {ai_text[:500]}"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.1,
            max_tokens=500,
        )

        raw = response.choices[0].message.content.strip()
        # Убираем markdown
        import re
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        facts = json.loads(raw)
        if facts and isinstance(facts, list):
            save_facts(user_id, facts)

    except Exception:
        # Ошибка извлечения не должна влиять на работу бота
        pass
