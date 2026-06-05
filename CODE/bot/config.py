"""
config.py — Config_Loader (Загрузчик настроек)
================================================

ПРОСТЫМИ СЛОВАМИ:
Это единственное место в проекте, которое знает секретные ключи (токены)
и пути к папкам с данными. Все остальные файлы спрашивают токены ТОЛЬКО здесь.

Токены НЕ записаны в коде. Они читаются из файла .env (или из окружения Docker).
Если какой-то токен забыли указать — бот не запустится и честно скажет, чего не хватает.
"""

import os
import sys
from pathlib import Path

# --------------------------------------------------
# Библиотека для чтения файла .env
# --------------------------------------------------
# Если библиотека python-dotenv не установлена — показываем понятную инструкцию
# и останавливаемся, вместо непонятной технической ошибки.
try:
    from dotenv import load_dotenv
except ImportError:
    print(
        "ОШИБКА: не установлена библиотека 'python-dotenv'.\n"
        "Установите её командой:\n"
        "    pip install python-dotenv\n"
        "или установите все зависимости сразу:\n"
        "    pip install -r requirements.txt"
    )
    sys.exit(1)

# --------------------------------------------------
# ПУТИ К ПАПКАМ
# --------------------------------------------------
# BASE_DIR — корень проекта. Этот файл лежит в /app/bot/config.py,
# поэтому корень — на одну папку выше (/app).
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# --------------------------------------------------
# ЗАГРУЗКА ФАЙЛА .env
# --------------------------------------------------
# override=False означает: если переменная уже задана в системе (например,
# передана в Docker), то значение из системы ВАЖНЕЕ, чем из файла .env.
# Загружаем .env ПЕРВЫМ делом, чтобы все настройки ниже могли его использовать.
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

# DATA_DIR — где хранятся все данные (база, документы, голос, бэкапы).
# По умолчанию это папка /app/data. При необходимости путь можно поменять,
# задав переменную окружения SENSEI_DATA_DIR (например, оставить данные в /app).
DATA_DIR: Path = Path(os.environ.get("SENSEI_DATA_DIR", str(BASE_DIR / "data")))

DB_PATH: Path = DATA_DIR / "memory.db"      # файл базы данных
VOICE_DIR: Path = DATA_DIR / "voice"        # временные голосовые файлы
DOCS_DIR: Path = DATA_DIR / "docs"          # сгенерированные документы DOCX
BACKUPS_DIR: Path = DATA_DIR / "backups"    # резервные копии базы данных


def _require_env(name: str) -> str:
    """
    Возвращает значение переменной окружения по имени.
    Если значение пустое или отсутствует — печатает понятную ошибку
    и останавливает бота (sys.exit).
    """
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"ОШИБКА: переменная окружения {name} не задана.\n"
            f"Добавьте строку {name}=<значение> в файл .env "
            f"(или передайте её в окружение Docker)."
        )
        sys.exit(1)
    return value


# --------------------------------------------------
# ТОКЕНЫ
# --------------------------------------------------
# Проверяем по очереди. Если не хватает первого — останавливаемся сразу на нём.
TELEGRAM_TOKEN: str = _require_env("TELEGRAM_TOKEN")
OPENAI_API_KEY: str = _require_env("OPENAI_API_KEY")

# --------------------------------------------------
# РЕЗЕРВНОЕ КОПИРОВАНИЕ ПАМЯТИ В TELEGRAM-КАНАЛ
# --------------------------------------------------
# ID приватного канала, куда бот будет слать копии памяти (memory.db) и экспорт.
# Если не задан (пусто) — отправка в канал просто отключена, бот работает как обычно.
# Это НЕ обязательная настройка, поэтому используем .get(), а не _require_env().
BACKUP_CHANNEL_ID: str = os.environ.get("BACKUP_CHANNEL_ID", "").strip()

# Выключатель отправки копий. Если BACKUP_ENABLED=false (без учёта регистра) —
# отправка в канал отключена, даже если BACKUP_CHANNEL_ID задан.
# По умолчанию (переменная не задана) — отправка включена.
BACKUP_ENABLED: bool = os.environ.get("BACKUP_ENABLED", "true").strip().lower() != "false"

# Как часто слать копию в канал автоматически (в секундах). По умолчанию раз в час.
# (Используется существующим локальным циклом и как запасное значение.)
try:
    BACKUP_INTERVAL_SECONDS: int = int(os.environ.get("BACKUP_INTERVAL_SECONDS", "3600"))
except ValueError:
    BACKUP_INTERVAL_SECONDS = 3600

# Интервал внешних копий БАЗЫ и ТЕКСТОВОГО ЭКСПОРТА в канал. По умолчанию 6 часов.
try:
    BACKUP_DB_INTERVAL_SECONDS: int = int(
        os.environ.get("BACKUP_DB_INTERVAL_SECONDS", "21600")
    )
except ValueError:
    BACKUP_DB_INTERVAL_SECONDS = 21600

# Интервал отправки АРХИВА КОДА в канал. По умолчанию раз в неделю (7 дней).
try:
    BACKUP_CODE_INTERVAL_SECONDS: int = int(
        os.environ.get("BACKUP_CODE_INTERVAL_SECONDS", "604800")
    )
except ValueError:
    BACKUP_CODE_INTERVAL_SECONDS = 604800

# Файл, где запоминается время последней успешной отправки каждого типа копии.
# Нужен, чтобы расписание переживало перезапуски контейнера/сервера
# (после долгого простоя копия уходит при первой возможности).
BACKUP_STATE_PATH: Path = DATA_DIR / "backup_state.json"

# Лимит размера файла для Telegram Bot API (sendDocument) — 50 МБ.
TELEGRAM_FILE_LIMIT_BYTES: int = 50 * 1024 * 1024


def backup_to_channel_enabled() -> bool:
    """True, если отправка копий в канал включена и канал задан."""
    return BACKUP_ENABLED and bool(BACKUP_CHANNEL_ID)
