# Implementation Plan: Sensei — модульная архитектура + токены из .env

## Overview

План превращает монолитный `main.py` (~450 строк) в модульный пакет `bot/` и переносит
захардкоженные токены в `.env` (через `python-dotenv`), не ломая существующий функционал.

Принцип реализации (из правил проекта): **Стабильность > Красота > Новые функции.**
Каждый шаг инкрементален и строится на предыдущем; логика из текущего `main.py`
переносится дословно, кроме явно описанного исправления коллизии `/task` ↔ `/tasks`.

Гарантии плана:
- **Обратимость.** Самый первый шаг — резервная копия оригинального `main.py`. Замена
  `main.py` на shim происходит только в самом конце, когда вся новая структура готова.
- **Нулевая поломка.** Слои создаются снизу вверх (config → database → utils → services
  → handlers → entry), поэтому каждый файл можно создать и проверить отдельно.
- **Безопасность секретов.** В git коммитятся только placeholder-значения
  (`.env.example`), реальный `.env` добавляется в `.gitignore`.

Язык реализации — **Python** (явно задан в design.md). Согласно разделу Testing Strategy
дизайна, property-based тестирование для этой фичи **не применяется** — используются
unit-тесты конфигурации (`pytest` + `monkeypatch`) и документированный чек-лист
дымовых проверок.

## Tasks

- [ ] 1. Резервная копия и каркас модульной структуры
  - [ ] 1.1 Создать бэкап оригинала и пустой каркас пакета
    - Скопировать текущий `main.py` в `backups/main.py.bak` (точка отката, оригинал не трогаем)
    - Создать каталоги: `bot/`, `bot/handlers/`, `bot/services/`, `bot/database/`, `bot/utils/`, `data/`, `data/backups/`, `data/docs/`, `data/voice/`
    - Создать пустые `__init__.py` в `bot/`, `bot/handlers/`, `bot/services/`, `bot/database/`, `bot/utils/` (делают каталоги Python-пакетами)
    - Добавить `.gitkeep` в `data/backups/`, `data/docs/`, `data/voice/`, чтобы пустые каталоги попали в репозиторий
    - _Requirements: 5.1, 5.2, 5.7, 7.2_

- [ ] 2. Конфигурация, секреты и зависимости
  - [ ] 2.1 Реализовать `bot/config.py` (Config_Loader)
    - Перехватить `ImportError` от `dotenv` и завершиться с понятной инструкцией по установке
    - Вычислить `BASE_DIR`, `DATA_DIR` (с переопределением через env `SENSEI_DATA_DIR`), `DB_PATH`, `VOICE_DIR`, `DOCS_DIR`, `BACKUPS_DIR`
    - Вызвать `load_dotenv(dotenv_path=BASE_DIR/".env", override=False)` (системные env приоритетнее `.env`)
    - Реализовать `_require_env(name)`: пустое/отсутствующее значение → понятное сообщение + `sys.exit(1)`
    - Последовательно прочитать `TELEGRAM_TOKEN`, затем `OPENAI_API_KEY` (падение на первом отсутствующем)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.5, 4.3, 8.2, 8.3_

  - [ ]* 2.2 Написать unit-тесты для `bot/config.py`
    - Использовать `pytest` + `monkeypatch`, перезагружая модуль `bot.config` с подменой env
    - `test_missing_telegram_token_exits` → `SystemExit`, сообщение упоминает `TELEGRAM_TOKEN`
    - `test_missing_openai_token_exits` → задан только `TELEGRAM_TOKEN`, `SystemExit` упоминает `OPENAI_API_KEY`
    - `test_sequential_check_order` → оба отсутствуют, падает первым на `TELEGRAM_TOKEN`
    - `test_system_env_overrides_dotenv` → разные значения в env и `.env`, используется системное
    - `test_tokens_loaded_from_dotenv` → env пуст, `.env` заполнен, токены прочитаны успешно
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.5, 4.3, 8.3_

  - [ ] 2.3 Создать `.env`, `.env.example` и `.gitignore`
    - `.env` — реальные значения `TELEGRAM_TOKEN=...` и `OPENAI_API_KEY=...` (взять из `backups/main.py.bak`); файл НЕ коммитится
    - `.env.example` — те же ключи с placeholder-значениями (`your-telegram-bot-token-here`, `your-openai-api-key-here`)
    - `.gitignore` — добавить `.env`, `data/`, `__pycache__/`, `*.pyc`, `*.bak`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2_

  - [ ] 2.4 Добавить `python-dotenv` в `requirements.txt`
    - Дописать строку `python-dotenv` в существующий `requirements.txt`, не меняя остальные зависимости
    - _Requirements: 8.1_

- [ ] 3. Слой базы данных
  - [ ] 3.1 Реализовать `bot/database/db.py`
    - `get_connection()`: создать `config.DATA_DIR` (`mkdir parents/exist_ok`), вернуть `sqlite3.connect(config.DB_PATH, check_same_thread=False)`
    - `init_db(connection)`: создать таблицы `memory`, `tasks`, `reminders` через `CREATE TABLE IF NOT EXISTS` (схема дословно из `main.py`)
    - На уровне модуля создать общие `conn`, `cursor` и вызвать `init_db(conn)` (как в оригинале)
    - _Requirements: 5.6, 6.6_

- [ ] 4. Вспомогательный слой (utils)
  - [ ] 4.1 Реализовать `bot/utils/folders.py`
    - `ensure_folders()`: создать `DATA_DIR`, `VOICE_DIR`, `DOCS_DIR`, `BACKUPS_DIR` с `exist_ok=True`
    - _Requirements: 6.5, 6.7_

  - [ ] 4.2 Реализовать `bot/utils/docx.py`
    - `save_docx(user_id, user_text, ai_text)`: DOCX с диалогом в `config.DOCS_DIR`, вернуть путь
    - `save_voice_transcript(user_id, text)`: DOCX с транскриптом в `config.DOCS_DIR`, вернуть путь
    - Логику генерации перенести из `main.py` дословно
    - _Requirements: 6.7_

- [ ] 5. Сервисный слой (бизнес-логика)
  - [ ] 5.1 Реализовать `bot/services/memory.py`
    - `save_memory(user_id, role, content)` и `load_memory(user_id, limit=15)` через `db.cursor`/`db.conn`
    - Сохранить порядок: последние 15 сообщений в хронологическом порядке
    - _Requirements: 6.2_

  - [ ] 5.2 Реализовать `bot/services/tasks.py`
    - `add_task(user_id, task_text)` — INSERT со статусом `active`
    - `list_tasks(user_id)` — вернуть `[(id, task), ...]` активных задач
    - _Requirements: 6.1_

  - [ ] 5.3 Реализовать `bot/services/reminders.py`
    - `add_reminder(user_id, remind_time, reminder_text)` — INSERT в `reminders`
    - `reminder_loop(bot)` — каждые 30 сек искать `remind_time<=now AND sent=0`, отправлять, помечать `sent=1`; широкий `try/except` + `sleep(30)`
    - `bot` принимается аргументом (без глобальной зависимости)
    - _Requirements: 6.1, 6.4_

  - [ ] 5.4 Реализовать `bot/services/backup.py`
    - `backup_loop()` — раз в час копировать `config.DB_PATH` в `config.BACKUPS_DIR/backup_<timestamp>.db`; широкий `try/except` + `sleep(3600)`
    - _Requirements: 6.5_

  - [ ] 5.5 Реализовать `bot/services/ai.py`
    - Создать `client = OpenAI(api_key=config.OPENAI_API_KEY)`
    - Перенести `SYSTEM_PROMPT` из `main.py` **дословно** (без правок текста)
    - `ask_ai(user_id, text)`: сохранить в память → вызвать `gpt-4.1-mini` с системным промптом + историей → сохранить ответ → сгенерировать DOCX (`utils/docx.save_docx`) → вернуть ответ
    - _Requirements: 3.3, 6.2, 6.7_

- [ ] 6. Контрольная точка — проверка нижних слоёв
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Слой обработчиков (handlers)
  - [ ] 7.1 Реализовать `bot/handlers/commands.py`
    - `register(bot)` с тремя хэндлерами: `commands=['task']`, `commands=['tasks']`, `commands=['remind']`
    - `/task` → текст после команды в `add_task()`, ответ «✅ Задача добавлена»
    - `/tasks` → `list_tasks()` → форматированный список (точное сопоставление исправляет коллизию `/task`↔`/tasks`)
    - `/remind` → разбор `время | текст` → `add_reminder()`; при ошибке формата подсказка `/remind 2026-05-25 18:00 | Текст`
    - _Requirements: 6.1_

  - [ ] 7.2 Реализовать `bot/handlers/text.py`
    - `register(bot)` с хэндлером `func=lambda m: m.content_type=='text' and not m.text.startswith('/')`
    - Вызвать `ask_ai(message.chat.id, message.text)`, ответить; `try/except` → `bot.reply_to(message, f"Ошибка:\n{e}")`
    - _Requirements: 6.2_

  - [ ] 7.3 Реализовать `bot/handlers/voice.py`
    - `register(bot)` с хэндлером `content_types=['voice']`
    - Скачать ogg в `config.VOICE_DIR` → конвертация в wav через `pydub` → транскрипция `whisper-1` → `ask_ai()` → `save_voice_transcript()` → отправка документа и ответа; `try/except` → `f"Voice error:\n{e}"`
    - _Requirements: 6.3, 6.7_

- [ ] 8. Точка входа и совместимость с продакшеном
  - [ ] 8.1 Реализовать `bot/main.py` (`main()`)
    - Импортировать `config`, `database.db` (создаёт conn+таблицы), `utils.folders`, хэндлеры, циклы напоминаний/бэкапов
    - `main()`: `ensure_folders()` → создать `telebot.TeleBot(config.TELEGRAM_TOKEN)` → `register()` всех хэндлеров → запустить демон-потоки `reminder_loop(bot)` и `backup_loop` → `print("AI OS STARTED")` → `bot.infinity_polling()`
    - Добавить `if __name__ == "__main__": main()`
    - _Requirements: 3.3, 3.4, 5.3, 6.4, 6.5_

  - [ ] 8.2 Заменить корневой `main.py` на shim
    - Перезаписать `main.py` тремя строками: `from bot.main import main` и `if __name__ == "__main__": main()`
    - Убедиться, что в новом `main.py` НЕТ захардкоженных токенов (импорт идёт только через Config_Loader)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.2, 4.4_

- [ ] 9. Документация структуры и миграции
  - [ ] 9.1 Создать `STRUCTURE.md`
    - Полное дерево файлов с описанием назначения каждого каталога/файла
    - Явно указать, что добавление новых модулей в `handlers/`/`services/` не требует изменения существующих
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 9.2 Создать `MIGRATION_CHECKLIST.md` (чек-лист миграции и дымовых проверок)
    - Шаги бэкапа (`main.py.bak`, `memory.db.bak`), запуск с `--env-file`, короткий рестарт и откат — из раздела Migration Strategy дизайна
    - Дымовой чек-лист (текст/память/`/task`/`/tasks`/`/remind`/голос/циклы) и проверки сохранности схемы и данных БД
    - _Requirements: 4.1, 4.4, 6.6_

- [ ] 10. Финальная контрольная точка
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Задачи, помеченные `*` (только 2.2), — опциональные unit-тесты, их можно пропустить для быстрого MVP.
- Property-based тесты **не используются** (см. Testing Strategy дизайна): фича — это загрузка конфигурации, структурный рефакторинг и документация.
- Каждая задача ссылается на конкретные пункты требований для трассируемости.
- Слои создаются снизу вверх, поэтому интеграция в `bot/main.py` (задача 8.1) собирает уже готовые и проверенные модули — без «висячего» кода.
- Замена корневого `main.py` на shim (8.2) — последний шаг кода, что сохраняет обратимость до самого конца.
- Перенос рабочей `memory.db` под `data/` и развёртывание на VPS выполняются по `MIGRATION_CHECKLIST.md` вручную (это деплой, а не задача для кодового агента).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.3", "2.4", "9.1"] },
    { "id": 2, "tasks": ["2.2", "3.1", "4.1", "4.2", "5.4"] },
    { "id": 3, "tasks": ["5.1", "5.2", "5.3"] },
    { "id": 4, "tasks": ["5.5", "7.1"] },
    { "id": 5, "tasks": ["7.2", "7.3"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2", "9.2"] }
  ]
}
```
