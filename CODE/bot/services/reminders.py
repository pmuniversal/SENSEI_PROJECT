"""
reminders.py — Напоминания
===========================

ПРОСТЫМИ СЛОВАМИ:
Здесь бот сохраняет напоминания и в фоне (отдельным процессом) каждые 30 секунд
проверяет: не пора ли отправить какое-нибудь напоминание. Если пора — отправляет
и помечает его как отправленное, чтобы не слать дважды.
"""

import time
from datetime import datetime

from bot.database import db


def add_reminder(user_id, remind_time: str, reminder_text: str) -> None:
    """Сохраняет новое напоминание на указанное время."""
    db.cursor.execute(
        """
        INSERT INTO reminders
        (user_id, reminder, remind_time)
        VALUES (?, ?, ?)
        """,
        (
            str(user_id),
            reminder_text,
            remind_time,
        ),
    )
    db.conn.commit()


def reminder_loop(bot) -> None:
    """
    Бесконечный фоновый цикл проверки напоминаний (каждые 30 секунд).

    `bot` передаётся аргументом, чтобы этот файл не зависел напрямую
    от точки запуска (так структуру проще расширять в будущем).
    """
    while True:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            db.cursor.execute(
                """
                SELECT id, user_id, reminder
                FROM reminders
                WHERE remind_time<=?
                AND sent=0
                """,
                (now,),
            )

            rows = db.cursor.fetchall()

            for row in rows:
                reminder_id = row[0]
                user_id = row[1]
                reminder_text = row[2]

                bot.send_message(
                    user_id,
                    f"⏰ НАПОМИНАНИЕ:\n\n{reminder_text}",
                )

                db.cursor.execute(
                    """
                    UPDATE reminders
                    SET sent=1
                    WHERE id=?
                    """,
                    (reminder_id,),
                )
                db.conn.commit()

        except Exception:
            pass

        time.sleep(30)
