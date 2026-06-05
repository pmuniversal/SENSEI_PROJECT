"""
folders.py — Создание рабочих папок
=====================================

ПРОСТЫМИ СЛОВАМИ:
Перед стартом бот должен убедиться, что все нужные папки существуют
(для данных, голоса, документов и бэкапов). Если их нет — создаём.
Если уже есть — ничего не ломаем.
"""

from bot import config


def ensure_folders() -> None:
    """Создаёт все нужные папки данных (если их ещё нет)."""
    for folder in (
        config.DATA_DIR,
        config.VOICE_DIR,
        config.DOCS_DIR,
        config.BACKUPS_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)
