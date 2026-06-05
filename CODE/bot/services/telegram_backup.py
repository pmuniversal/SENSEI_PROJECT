"""
telegram_backup.py — Внешние копии памяти и кода в Telegram-канал (Этап 1)
===========================================================================

ПРОСТЫМИ СЛОВАМИ:
Самое ценное — это память (memory.db). Локальные копии лежат на том же сервере,
и если сервер умрёт — пропадёт всё. Этот модуль шлёт копии «наружу», в приватный
Telegram-канал, где бот — администратор.

Что делает:
  • каждые 6 часов  → отправляет в канал файл базы memory.db + текстовый экспорт памяти
  • раз в неделю    → отправляет в канал .zip-архив кода бота (папка bot/), без секретов
  • по команде      → /backup или фраза «сделай копию сейчас» — мгновенная отправка

ПРИНЦИПЫ:
  • Это НОВЫЙ отдельный модуль. Существующий код не меняется.
  • Любая ошибка (сеть, Telegram, большой файл) логируется и НЕ роняет бота.
  • Расписание переживает перезапуски: время последней отправки хранится в файле
    backup_state.json. После долгого простоя копия уходит при первом запуске.
  • Секреты (.env, токены) НЕ попадают ни в архив, ни в лог.
"""

import io
import json
import os
import time
import zipfile
from datetime import datetime, timezone

from bot import config
from bot.utils.export import build_memory_export


# --------------------------------------------------
# Вспомогательное: лог без раскрытия секретов
# --------------------------------------------------
def _log(message: str) -> None:
    """Печатает сообщение в стандартный вывод (его видно в docker logs)."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[BACKUP {ts}] {message}", flush=True)
    except Exception:
        # Сбой логирования не должен влиять на работу циклов.
        pass


def _utc_caption(prefix: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"{prefix}\n🕒 {now}"


# --------------------------------------------------
# Состояние расписания (переживает перезапуски)
# --------------------------------------------------
def _load_state() -> dict:
    try:
        if config.BACKUP_STATE_PATH.exists():
            with open(config.BACKUP_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        _log(f"Не удалось прочитать состояние расписания: {e}")
    return {}


def _save_state(state: dict) -> None:
    try:
        config.BACKUP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(config.BACKUP_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        _log(f"Не удалось сохранить состояние расписания: {e}")


# --------------------------------------------------
# Создание архива кода (в памяти, без секретов)
# --------------------------------------------------
# Что исключаем из архива кода: секреты, базы, временные данные, кэш.
_EXCLUDE_NAMES = {".env", "__pycache__", "backup_state.json"}
_EXCLUDE_EXT = {".pyc", ".db", ".bak"}
_EXCLUDE_DIRS = {"data", "backups", ".git"}


def _build_code_archive() -> bytes:
    """
    Собирает .zip с кодом бота (папка bot/) в оперативной памяти и возвращает байты.
    .env, базы данных и папка data/ НЕ включаются.
    """
    base_dir = config.BASE_DIR
    bot_dir = base_dir / "bot"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(bot_dir):
            # отфильтровать нежелательные подпапки
            dirs[:] = [
                d for d in dirs
                if d not in _EXCLUDE_DIRS and d not in _EXCLUDE_NAMES
            ]
            for name in files:
                if name in _EXCLUDE_NAMES:
                    continue
                if os.path.splitext(name)[1] in _EXCLUDE_EXT:
                    continue
                full = os.path.join(root, name)
                # путь внутри архива — относительно корня проекта (bot/...)
                arcname = os.path.relpath(full, base_dir)
                try:
                    zf.write(full, arcname)
                except Exception as e:
                    _log(f"Файл пропущен при архивации ({arcname}): {e}")
    buffer.seek(0)
    return buffer.read()


# --------------------------------------------------
# Отправка отдельных типов копий
# --------------------------------------------------
def send_db(bot) -> bool:
    """Отправляет файл базы memory.db в канал. Возвращает True при успехе."""
    db_path = config.DB_PATH
    if not db_path.exists():
        _log(f"Пропуск: файл базы не найден ({db_path}).")
        return False

    size = db_path.stat().st_size
    if size > config.TELEGRAM_FILE_LIMIT_BYTES:
        _log(f"Пропуск базы: размер {size} байт превышает лимит Telegram 50 МБ.")
        return False

    try:
        with open(db_path, "rb") as f:
            bot.send_document(
                config.BACKUP_CHANNEL_ID,
                f,
                visible_file_name="memory.db",
                caption=_utc_caption("💾 Копия базы памяти (memory.db)"),
            )
        _log("Успех: база memory.db отправлена в канал.")
        return True
    except Exception as e:
        _log(f"Ошибка отправки базы: {e}")
        return False


def send_export(bot) -> bool:
    """Формирует и отправляет текстовый экспорт памяти. True при успехе."""
    try:
        text = build_memory_export()
    except Exception as e:
        _log(f"Ошибка формирования экспорта (база): {e}. Экспорт пропущен.")
        return False

    try:
        data = text.encode("utf-8")
        if len(data) > config.TELEGRAM_FILE_LIMIT_BYTES:
            _log("Пропуск экспорта: файл превышает лимит Telegram 50 МБ.")
            return False
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        bio = io.BytesIO(data)
        bio.name = f"memory_export_{stamp}.md"
        bot.send_document(
            config.BACKUP_CHANNEL_ID,
            bio,
            visible_file_name=bio.name,
            caption=_utc_caption("🧠 Текстовый экспорт памяти"),
        )
        _log("Успех: текстовый экспорт памяти отправлен в канал.")
        return True
    except Exception as e:
        _log(f"Ошибка отправки экспорта: {e}")
        return False


def send_code(bot) -> bool:
    """Создаёт и отправляет .zip-архив кода бота. True при успехе."""
    try:
        archive = _build_code_archive()
    except Exception as e:
        _log(f"Ошибка создания архива кода: {e}")
        return False

    if len(archive) > config.TELEGRAM_FILE_LIMIT_BYTES:
        _log("Пропуск архива кода: размер превышает лимит Telegram 50 МБ.")
        return False

    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        bio = io.BytesIO(archive)
        bio.name = f"sensei_code_{stamp}.zip"
        bot.send_document(
            config.BACKUP_CHANNEL_ID,
            bio,
            visible_file_name=bio.name,
            caption=_utc_caption("📦 Архив кода бота (без секретов)"),
        )
        _log("Успех: архив кода отправлен в канал.")
        return True
    except Exception as e:
        _log(f"Ошибка отправки архива кода: {e}")
        return False


# --------------------------------------------------
# Копия по запросу (команда /backup или фраза)
# --------------------------------------------------
def run_on_demand_backup(bot, chat_id) -> None:
    """
    Немедленно отправляет базу + экспорт в канал и пишет пользователю статус.
    Используется обработчиком команды /backup и фразы «сделай копию сейчас».
    """
    if not config.backup_to_channel_enabled():
        try:
            bot.send_message(
                chat_id,
                "⚠️ Канал для копий не настроен (BACKUP_CHANNEL_ID). "
                "Копия не отправлена, но бот работает как обычно.",
            )
        except Exception as e:
            _log(f"Не удалось уведомить о ненастроенном канале: {e}")
        return

    try:
        bot.send_message(chat_id, "📤 Отправляю копию...")
    except Exception as e:
        _log(f"Не удалось отправить уведомление о старте копии: {e}")

    ok_db = send_db(bot)
    ok_export = send_export(bot)

    # обновим состояние расписания, чтобы плановые отправки не дублировались
    if ok_db or ok_export:
        state = _load_state()
        now = int(time.time())
        if ok_db:
            state["last_db"] = now
        if ok_export:
            state["last_export"] = now
        _save_state(state)

    try:
        if ok_db and ok_export:
            bot.send_message(chat_id, "✅ Копия отправлена в канал")
        elif ok_db or ok_export:
            bot.send_message(
                chat_id,
                "⚠️ Копия отправлена частично. Подробности — в логах бота.",
            )
        else:
            bot.send_message(
                chat_id,
                "❌ Не удалось отправить копию. Подробности — в логах бота.",
            )
    except Exception as e:
        _log(f"Не удалось отправить итоговый статус: {e}")


# --------------------------------------------------
# Фоновый цикл расписания
# --------------------------------------------------
def backup_offsite_loop(bot) -> None:
    """
    Бесконечный фоновый цикл (поток-демон). Проверяет раз в минуту, не пора ли
    отправить очередную копию по расписанию, и отправляет нужные типы.

    Расписание переживает перезапуски: время последней отправки хранится
    в backup_state.json. После долгого простоя копия уходит при первой проверке.
    """
    if not config.backup_to_channel_enabled():
        _log("Внешние копии в канал отключены (нет BACKUP_CHANNEL_ID или BACKUP_ENABLED=false).")
        return

    _log("Цикл внешних копий запущен.")

    while True:
        try:
            state = _load_state()
            now = int(time.time())

            # База memory.db — каждые BACKUP_DB_INTERVAL_SECONDS (по умолчанию 6 ч)
            if now - int(state.get("last_db", 0)) >= config.BACKUP_DB_INTERVAL_SECONDS:
                if send_db(bot):
                    state["last_db"] = now
                    _save_state(state)

            # Текстовый экспорт — тот же интервал, вместе с базой
            if now - int(state.get("last_export", 0)) >= config.BACKUP_DB_INTERVAL_SECONDS:
                if send_export(bot):
                    state["last_export"] = now
                    _save_state(state)

            # Архив кода — раз в неделю
            if now - int(state.get("last_code", 0)) >= config.BACKUP_CODE_INTERVAL_SECONDS:
                if send_code(bot):
                    state["last_code"] = now
                    _save_state(state)

        except Exception as e:
            # Любая непредвиденная ошибка не должна останавливать поток.
            _log(f"Непредвиденная ошибка в цикле копий: {e}")

        # Ждём минуту до следующей проверки (не нагружает процессор).
        time.sleep(60)
