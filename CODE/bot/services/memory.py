"""
memory.py — Долговременная память бота
========================================

ПРОСТЫМИ СЛОВАМИ:
Здесь бот сохраняет каждое сообщение (твоё и своё) в базу данных
и умеет доставать последние сообщения, чтобы помнить контекст разговора.
По умолчанию помнит последние 15 сообщений.
"""

from datetime import datetime

from bot.database import db


def save_memory(user_id, role: str, content: str) -> None:
    """Сохраняет одно сообщение в память (роль: 'user' или 'assistant')."""
    db.cursor.execute(
        """
        INSERT INTO memory
        (user_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(user_id),
            role,
            content,
            str(datetime.now()),
        ),
    )
    db.conn.commit()


def load_memory(user_id, limit: int = 15) -> list[dict]:
    """
    Загружает последние `limit` сообщений пользователя
    в правильном (хронологическом) порядке — от старых к новым.
    """
    db.cursor.execute(
        """
        SELECT role, content
        FROM memory
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            str(user_id),
            limit,
        ),
    )

    rows = db.cursor.fetchall()
    rows.reverse()

    messages = []
    for row in rows:
        messages.append({
            "role": row[0],
            "content": row[1],
        })

    return messages
