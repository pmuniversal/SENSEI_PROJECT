"""
reminders.py — Напоминания
===========================

Фоновый цикл каждые 30 сек проверяет и отправляет напоминания.
Нормализует разные форматы времени (YYYY-MM-DD HH:MM, HH:MM, сегодня, завтра и т.д.)
"""

import time
import re
from datetime import datetime, date, timedelta

from bot.database import db


def _normalize_remind_time(raw: str) -> str | None:
    """
    Нормализует время напоминания в формат 'YYYY-MM-DD HH:MM'.
    Принимает:
      - '2026-06-16 15:25' → '2026-06-16 15:25'
      - '15:25' → сегодня 15:25
      - '16 июня 15:25', '16.06 15:25' и подобные → пробует разобрать
    """
    raw = raw.strip()
    now = datetime.now()

    # Уже правильный формат
    m = re.match(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})$', raw)
    if m:
        return raw

    # Только время HH:MM — берём сегодня
    m = re.match(r'^(\d{1,2}):(\d{2})$', raw)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        dt = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if dt < now:
            dt += timedelta(days=1)
        return dt.strftime('%Y-%m-%d %H:%M')

    # YYYY-MM-DD без времени — ставим 09:00
    m = re.match(r'^(\d{4}-\d{2}-\d{2})$', raw)
    if m:
        return raw + ' 09:00'

    # Попробуем через datetime.fromisoformat
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M']:
        try:
            dt = datetime.strptime(raw[:19], fmt)
            return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass

    # Числовой формат дд.мм ЧЧ:ММ или дд.мм.гггг ЧЧ:ММ
    m = re.match(r'^(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{4}))?\s+(\d{1,2}):(\d{2})$', raw)
    if m:
        day, mon = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        h, mi = int(m.group(4)), int(m.group(5))
        try:
            dt = datetime(year, mon, day, h, mi)
            return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass

    return None


def add_reminder(user_id, remind_time: str, reminder_text: str) -> str:
    """
    Сохраняет новое напоминание.
    Возвращает нормализованное время (для отображения пользователю).
    """
    normalized = _normalize_remind_time(remind_time) or remind_time
    db.cursor.execute(
        "INSERT INTO reminders (user_id, reminder, remind_time) VALUES (?, ?, ?)",
        (str(user_id), reminder_text, normalized),
    )
    db.conn.commit()
    return normalized


def list_reminders(user_id) -> list:
    """Возвращает активные (не отправленные) напоминания пользователя."""
    db.cursor.execute(
        "SELECT id, reminder, remind_time FROM reminders WHERE user_id=? AND sent=0 ORDER BY remind_time ASC",
        (str(user_id),)
    )
    return db.cursor.fetchall()


def delete_reminder(reminder_id: int, user_id) -> bool:
    """Удаляет напоминание по ID (только если принадлежит пользователю)."""
    db.cursor.execute(
        "DELETE FROM reminders WHERE id=? AND user_id=?",
        (reminder_id, str(user_id))
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


def reminder_loop(bot) -> None:
    """Фоновый цикл: каждые 30 сек проверяет и отправляет напоминания."""
    while True:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            db.cursor.execute(
                "SELECT id, user_id, reminder FROM reminders WHERE remind_time<=? AND sent=0",
                (now,),
            )
            rows = db.cursor.fetchall()
            for row in rows:
                rid, user_id, reminder_text = row
                try:
                    bot.send_message(user_id, f"⏰ *Напоминание:*\n\n{reminder_text}", parse_mode="Markdown")
                    db.cursor.execute("UPDATE reminders SET sent=1 WHERE id=?", (rid,))
                    db.conn.commit()
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(30)
