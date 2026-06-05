"""
backup.py — Автоматические резервные копии базы данных
=======================================================

ПРОСТЫМИ СЛОВАМИ:
Раз в час бот делает копию файла базы данных в папку data/backups.
Это страховка: если с базой что-то случится, есть свежая копия.
"""

import time

from bot import config


def backup_loop() -> None:
    """Бесконечный фоновый цикл: раз в час копирует базу данных в папку бэкапов."""
    while True:
        try:
            backup_name = config.BACKUPS_DIR / f"backup_{int(time.time())}.db"

            with open(config.DB_PATH, "rb") as src:
                with open(backup_name, "wb") as dst:
                    dst.write(src.read())

        except Exception:
            pass

        time.sleep(3600)
