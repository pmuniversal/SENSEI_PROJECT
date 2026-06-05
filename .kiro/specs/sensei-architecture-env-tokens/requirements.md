# Requirements Document

## Introduction

Данный документ описывает требования к двум ключевым изменениям проекта Sensei:
1. Перенос секретных токенов (TELEGRAM_TOKEN, OPENAI_API_KEY) из захардкоженных значений в main.py в переменные окружения через .env файл
2. Проектирование модульной файловой архитектуры проекта для будущего масштабирования

Оба изменения должны быть выполнены инкрементально, без нарушения текущей работоспособности бота, работающего в Docker-контейнере "simplerllm" на VPS (Oracle Cloud, Ubuntu 22.04) под управлением Supervisor.

## Glossary

- **Bot**: Telegram-бот Sensei, работающий как Python-процесс в Docker-контейнере
- **Config_Loader**: Модуль, отвечающий за загрузку конфигурации (токенов и настроек) из переменных окружения и .env файла
- **Env_File**: Файл `.env` в корне проекта, содержащий секретные переменные окружения в формате KEY=VALUE
- **Module**: Отдельный Python-файл, содержащий логически связанную функциональность (например, работа с задачами, напоминаниями, голосом)
- **Docker_Container**: Контейнер "simplerllm", в котором запускается Bot на VPS
- **Architecture**: Файловая и папочная структура проекта, определяющая расположение модулей, конфигурации и данных
- **Main_Entry**: Главный файл main.py, являющийся точкой входа приложения

## Requirements

### Requirement 1: Загрузка токенов из переменных окружения

**User Story:** As a developer, I want tokens to be loaded from environment variables, so that secrets are not exposed in source code and can be changed without modifying code.

#### Acceptance Criteria

1. WHEN the Bot starts, THE Config_Loader SHALL read TELEGRAM_TOKEN from environment variables
2. WHEN the Bot starts, THE Config_Loader SHALL read OPENAI_API_KEY from environment variables
3. IF TELEGRAM_TOKEN is not found in environment variables, THEN THE Config_Loader SHALL terminate the Bot with a clear error message indicating that TELEGRAM_TOKEN is missing
4. IF OPENAI_API_KEY is not found in environment variables, THEN THE Config_Loader SHALL terminate the Bot with a clear error message indicating that OPENAI_API_KEY is missing
5. THE Config_Loader SHALL check required tokens sequentially and terminate on the first missing token encountered
6. THE Config_Loader SHALL load variables from the Env_File located in the project root directory before checking environment variables

### Requirement 2: Создание .env файла для хранения секретов

**User Story:** As a developer, I want a .env file to store secrets locally, so that I can manage tokens separately from code and easily update them.

#### Acceptance Criteria

1. THE Env_File SHALL contain TELEGRAM_TOKEN in the format `TELEGRAM_TOKEN=<value>`
2. THE Env_File SHALL contain OPENAI_API_KEY in the format `OPENAI_API_KEY=<value>`
3. THE Architecture SHALL include a `.env.example` file with placeholder values showing the required variable names without actual secrets
4. THE Architecture SHALL include the Env_File path in `.gitignore` to prevent accidental commit of secrets
5. WHEN the Env_File is present, THE Config_Loader SHALL use values from the Env_File as environment variables

### Requirement 3: Удаление захардкоженных токенов из исходного кода

**User Story:** As a developer, I want hardcoded tokens removed from main.py, so that secrets are not visible in the source code.

#### Acceptance Criteria

1. THE Main_Entry SHALL NOT contain any hardcoded token values for TELEGRAM_TOKEN
2. THE Main_Entry SHALL NOT contain any hardcoded token values for OPENAI_API_KEY
3. THE Main_Entry SHALL import token values exclusively through the Config_Loader
4. WHEN tokens are removed from source code, THE Bot SHALL maintain identical functionality to the current version

### Requirement 4: Совместимость с Docker-окружением

**User Story:** As a developer, I want the token loading mechanism to work in Docker, so that the bot continues running on VPS without interruption.

#### Acceptance Criteria

1. THE Docker_Container SHALL support passing environment variables via the Env_File using `--env-file` flag or docker-compose `env_file` directive
2. WHEN the Docker_Container starts with environment variables set, THE Bot SHALL use those variables for authentication
3. THE Config_Loader SHALL prioritize system environment variables over values in the Env_File when both are present, even if system variables are empty or malformed
4. WHEN migrating from hardcoded tokens to environment variables, THE Bot SHALL require zero downtime (stop old version, set env vars, start new version)

### Requirement 5: Модульная файловая архитектура проекта

**User Story:** As a developer, I want a clear modular folder structure, so that future features can be added as separate modules without modifying the core.

#### Acceptance Criteria

1. THE Architecture SHALL organize code into the following top-level directories: `bot/` (source code), `data/` (runtime data), `config/` (configuration files)
2. THE Architecture SHALL split bot source code into modules: `handlers/` (Telegram message handlers), `services/` (business logic), `database/` (DB operations), `utils/` (helper functions)
3. THE Architecture SHALL place the Main_Entry at `bot/main.py` as the single entry point that imports and registers all modules
4. THE Architecture SHALL place handler modules as separate files: `handlers/text.py`, `handlers/voice.py`, `handlers/commands.py`
5. THE Architecture SHALL place service modules as separate files: `services/ai.py`, `services/memory.py`, `services/tasks.py`, `services/reminders.py`, `services/backup.py`
6. THE Architecture SHALL place database operations in `database/db.py` with connection management and table creation
7. THE Architecture SHALL maintain a flat module structure (maximum one level of nesting inside `bot/`) to keep the architecture simple and controllable

### Requirement 6: Сохранение обратной совместимости при миграции

**User Story:** As a developer, I want the migration to be incremental, so that existing functionality is never broken during the transition.

#### Acceptance Criteria

1. WHEN migrating to modular architecture, THE Bot SHALL preserve all existing commands: /task, /tasks, /remind
2. WHEN migrating to modular architecture, THE Bot SHALL preserve text message handling with AI responses
3. WHEN migrating to modular architecture, THE Bot SHALL preserve voice message handling with Whisper transcription
4. WHEN migrating to modular architecture, THE Bot SHALL preserve the reminder background loop with 30-second check interval
5. WHEN migrating to modular architecture, THE Bot SHALL preserve the backup background loop with 1-hour interval
6. WHEN migrating to modular architecture, THE Bot SHALL preserve SQLite database schema (memory, tasks, reminders tables) without data loss
7. WHEN migrating to modular architecture, THE Bot SHALL preserve DOCX document generation for each AI response

### Requirement 7: Документация целевой структуры проекта

**User Story:** As a developer, I want a documented target file tree, so that I have a clear reference for where each component belongs.

#### Acceptance Criteria

1. THE Architecture SHALL include a `STRUCTURE.md` file in the project root documenting the complete file tree with descriptions of each directory and file purpose
2. THE Architecture SHALL define the following target file tree structure:
   ```
   /app/
   ├── .env
   ├── .env.example
   ├── .gitignore
   ├── requirements.txt
   ├── STRUCTURE.md
   ├── bot/
   │   ├── __init__.py
   │   ├── main.py
   │   ├── config.py
   │   ├── handlers/
   │   │   ├── __init__.py
   │   │   ├── text.py
   │   │   ├── voice.py
   │   │   └── commands.py
   │   ├── services/
   │   │   ├── __init__.py
   │   │   ├── ai.py
   │   │   ├── memory.py
   │   │   ├── tasks.py
   │   │   ├── reminders.py
   │   │   └── backup.py
   │   ├── database/
   │   │   ├── __init__.py
   │   │   └── db.py
   │   └── utils/
   │       ├── __init__.py
   │       └── folders.py
   └── data/
       ├── memory.db
       ├── backups/
       ├── docs/
       └── voice/
   ```
3. WHEN new modules are added in the future, THE Architecture SHALL allow adding new files in `handlers/` or `services/` without modifying existing modules

### Requirement 8: Зависимость python-dotenv

**User Story:** As a developer, I want python-dotenv added to dependencies, so that .env file loading works correctly.

#### Acceptance Criteria

1. THE Architecture SHALL include `python-dotenv` in requirements.txt
2. THE Config_Loader SHALL use python-dotenv library to load the Env_File
3. WHEN python-dotenv is not installed, THE Bot SHALL fail with a clear import error message at startup
