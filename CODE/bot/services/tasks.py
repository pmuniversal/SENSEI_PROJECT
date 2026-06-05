"""
tasks.py — Задачи
==================

ПРОСТЫМИ СЛОВАМИ:
Здесь бот добавляет новые задачи в базу и выдаёт список активных задач.
"""

from datetime import datetime

from bot.database import db


def add_task(user_id, task_text: str) -> None:
    """Добавляет новую задачу со статусом 'active' (активна)."""
    db.cursor.execute(
        """
        INSERT INTO tasks
        (user_id, task, status, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(user_id),
            task_text,
            "active",
            str(datetime.now()),
        ),
    )
    db.conn.commit()


def list_tasks(user_id) -> list[tuple]:
    """Возвращает список активных задач пользователя в виде [(id, текст), ...]."""
    db.cursor.execute(
        """
        SELECT id, task
        FROM tasks
        WHERE user_id=? AND status='active'
        """,
        (str(user_id),),
    )
    return db.cursor.fetchall()
