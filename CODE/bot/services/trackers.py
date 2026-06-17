"""
trackers.py — Трекеры личного развития (Этап 9)
=================================================

Трекинг привычек, сна, веса и «дешёвого дофамина»:
  - Ввод человеческим языком: «спал 7 часов», «вес 82», «залипал в тикток 2 часа»
  - Стрики: подряд N дней выполнения привычки
  - Еженедельный отчёт прогресса (в проактивности)
  - Запрос: «покажи привычки», «статистика сна», «сколько залипал»

Привычки создаются текстом: «привычка: читать 30 мин каждый день»
"""

import json
import re
from datetime import datetime, date, timedelta

from bot.database import db
from bot.services.ai import client


# ──────────────────────────────────────────────────
# Инициализация таблицы
# ──────────────────────────────────────────────────
def init_trackers_table():
    db.cursor.execute("""
    CREATE TABLE IF NOT EXISTS trackers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        type TEXT,       -- 'habit' | 'sleep' | 'weight' | 'dopamine' | 'energy'
        name TEXT,       -- название привычки или метрики
        value REAL,      -- значение (часы сна, кг, часы залипания, 1/0 для привычки)
        note TEXT,       -- комментарий
        date TEXT,       -- YYYY-MM-DD
        created_at TEXT
    )
    """)
    db.conn.commit()


init_trackers_table()


# ──────────────────────────────────────────────────
# Парсинг через GPT
# ──────────────────────────────────────────────────
def parse_tracker_input(text: str) -> dict | None:
    """Определяет тип трекера и данные из текста."""
    today = date.today().isoformat()
    system_prompt = f"""Дата: {today}. Определи тип трекера. Верни ТОЛЬКО JSON:

Если это ПРИВЫЧКА (привычка, habit, отметить):
{{"type": "habit", "name": "название привычки", "value": 1, "note": ""}}

Если это СОН (спал, сон, sleep):
{{"type": "sleep", "value": часы_сна, "note": ""}}

Если это ВЕС (вес, kg, weight):
{{"type": "weight", "value": число_кг, "note": ""}}

Если это ДОФАМИН / ЗАЛИПАНИЕ (залипал, тикток, ютуб, инста, соцсети, дофамин, dopamine):
{{"type": "dopamine", "name": "что именно", "value": часы, "note": ""}}

Если это ЭНЕРГИЯ (энергия, бодрость, energy, от 1 до 10):
{{"type": "energy", "value": число_1_до_10, "note": ""}}

Если это ЗАПРОС СТАТИСТИКИ (покажи привычки, статистика, стрик, отчёт трекеров):
{{"type": "query", "query_type": "habits|sleep|weight|dopamine|all"}}

Если это СОЗДАНИЕ ПРИВЫЧКИ (новая привычка, привычка:, habit:, отслеживать):
{{"type": "new_habit", "name": "название привычки"}}

Если НЕ про трекеры: {{"type": "none"}}
Верни ТОЛЬКО JSON."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=200,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        return None if data.get("type") == "none" else data
    except Exception:
        return None


# ──────────────────────────────────────────────────
# Операции
# ──────────────────────────────────────────────────
def log_tracker(user_id, data: dict) -> str:
    """Записывает данные трекера."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    t_type = data.get("type", "habit")
    name = data.get("name", t_type)
    value = data.get("value", 1)
    note = data.get("note", "")

    db.cursor.execute("""
    INSERT INTO trackers (user_id, type, name, value, note, date, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(user_id), t_type, name, value, note, today, str(now)))
    db.conn.commit()

    emoji = {"habit": "✅", "sleep": "😴", "weight": "⚖️", "dopamine": "🧠", "energy": "⚡"}
    e = emoji.get(t_type, "📊")

    if t_type == "habit":
        streak = _get_streak(user_id, name)
        streak_msg = f"🔥 Стрик: {streak} дней подряд"
        if streak >= 7:
            streak_msg += " 🏆 НЕДЕЛЯ!"
        elif streak >= 3:
            streak_msg += " 💪 Так держать!"
        return f"{e} *Привычка отмечена:* {name}\n{streak_msg}"
    elif t_type == "sleep":
        return f"{e} *Сон записан:* {value} часов"
    elif t_type == "weight":
        return f"{e} *Вес записан:* {value} кг"
    elif t_type == "dopamine":
        return f"{e} *Дофамин/залипание:* {name} — {value} ч\n⚠️ Контролируй это."
    elif t_type == "energy":
        return f"{e} *Энергия:* {value}/10"
    return f"{e} Записано: {name} = {value}"


def create_habit(user_id, name: str) -> str:
    """Создаёт новую привычку для отслеживания."""
    return f"🆕 *Привычка создана:* {name}\n\nОтмечай выполнение: «{name} сделано» или «отметить {name}»"


def _get_streak(user_id, habit_name: str) -> int:
    """Считает текущий стрик (дни подряд)."""
    db.cursor.execute("""
    SELECT DISTINCT date FROM trackers
    WHERE user_id=? AND type='habit' AND name=?
    ORDER BY date DESC LIMIT 30
    """, (str(user_id), habit_name))
    rows = db.cursor.fetchall()
    if not rows:
        return 1

    streak = 0
    check_date = date.today()
    dates_set = {r[0] for r in rows}

    for i in range(30):
        d = (check_date - timedelta(days=i)).isoformat()
        if d in dates_set:
            streak += 1
        else:
            break
    return max(streak, 1)


def get_tracker_stats(user_id, query_type: str = "all") -> str:
    """Статистика трекеров за последнюю неделю."""
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    lines = ["📊 *Статистика за неделю:*\n"]

    if query_type in ("habits", "all"):
        db.cursor.execute("""
        SELECT name, COUNT(DISTINCT date) as days FROM trackers
        WHERE user_id=? AND type='habit' AND date>=?
        GROUP BY name ORDER BY days DESC
        """, (str(user_id), week_ago))
        rows = db.cursor.fetchall()
        if rows:
            lines.append("*Привычки:*")
            for name, days in rows:
                streak = _get_streak(user_id, name)
                lines.append(f"  ✅ {name}: {days}/7 дней (стрик: {streak} 🔥)")
            lines.append("")

    if query_type in ("sleep", "all"):
        db.cursor.execute("""
        SELECT AVG(value), MIN(value), MAX(value) FROM trackers
        WHERE user_id=? AND type='sleep' AND date>=?
        """, (str(user_id), week_ago))
        row = db.cursor.fetchone()
        if row and row[0]:
            lines.append(f"*Сон:* среднее {row[0]:.1f}ч (мин {row[1]:.0f}, макс {row[2]:.0f})")
            lines.append("")

    if query_type in ("dopamine", "all"):
        db.cursor.execute("""
        SELECT name, SUM(value) as total FROM trackers
        WHERE user_id=? AND type='dopamine' AND date>=?
        GROUP BY name ORDER BY total DESC
        """, (str(user_id), week_ago))
        rows = db.cursor.fetchall()
        if rows:
            lines.append("*Дофамин/залипания:*")
            for name, total in rows:
                lines.append(f"  🧠 {name}: {total:.1f} ч за неделю")
            lines.append("")

    if query_type in ("weight", "all"):
        db.cursor.execute("""
        SELECT value, date FROM trackers
        WHERE user_id=? AND type='weight' AND date>=?
        ORDER BY date DESC LIMIT 1
        """, (str(user_id), week_ago))
        row = db.cursor.fetchone()
        if row:
            lines.append(f"*Вес:* {row[0]} кг ({row[1]})")

    if len(lines) == 1:
        return "📊 Нет данных за неделю. Начни отмечать: «спал 7 часов», «вес 82»."

    return "\n".join(lines)


# ──────────────────────────────────────────────────
# Главная функция
# ──────────────────────────────────────────────────
def process_tracker(user_id, text: str) -> str | None:
    """Обрабатывает трекер-ввод. None если не трекер."""
    data = parse_tracker_input(text)
    if data is None:
        return None

    t = data.get("type")
    if t in ("habit", "sleep", "weight", "dopamine", "energy"):
        return log_tracker(user_id, data)
    elif t == "new_habit":
        return create_habit(user_id, data.get("name", ""))
    elif t == "query":
        return get_tracker_stats(user_id, data.get("query_type", "all"))
    return None
