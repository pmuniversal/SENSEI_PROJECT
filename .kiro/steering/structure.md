---
inclusion: always
---

# SENSEI — навигация по файлам проекта

> Подгружается автоматически. Где что лежит в папке проекта (на Google Диске).
> Корень: `SENSEI_PROJECT/`

## Папки верхнего уровня

```
SENSEI_PROJECT/
├── .kiro/                  # steering (этот контекст) + специи (specs)
│   ├── steering/           # product.md, tech.md, structure.md, workflow.md  ← читаются всегда
│   └── specs/              # зеркало активных спеков (см. ниже)
├── CONTEXT/                # ЖИВАЯ ПАМЯТЬ проекта — читать в начале каждого чата
│   ├── START_HERE.md       # стартовая инструкция «как подключаться к проекту»
│   ├── SENSEI_MASTER_CONTEXT_v1.md  # полный контекст: статус, что сделано, цели
│   ├── PROJECT_CHANGELOG.md # журнал изменений (чекпоинты по датам)
│   ├── ROADMAP.md          # маршрут развития (этапы 1–14)
│   ├── BACKLOG.md          # склад идей + принципы владельца + деликатный контекст
│   ├── SENSEI_SYSTEM_PROMPT.md  # системный промпт самого бота-наставника
│   └── Clean State (прежний чат).md  # полный экспорт первого чата (история «как начинали»)
├── CODE/                   # ВЕСЬ код бота (см. tech.md и CODE/STRUCTURE.md)
│   └── .kiro/specs/        # рабочие спеки внутри кода (источник истины для кода)
├── DOCS/
│   └── ideas.md            # список идей по категориям
├── DATABASE/
│   └── future_sqlite/      # задел под будущее (пусто)
└── VPS/                    # всё про сервер
    ├── server_info.md      # IP, ОС, контейнер, дата запуска
    ├── deployment.md       # как разворачивать
    └── docker_commands.md  # шпаргалка команд Docker
```

## Где «источник истины» для кода

Спеки (requirements/design/tasks) для кода живут в `CODE/.kiro/specs/`.
В `SENSEI_PROJECT/.kiro/specs/` держим копию-зеркало активных спеков, чтобы
контекст не терялся при переносе папки целиком.

## Порядок чтения в начале нового чата (для ИИ)

1. Steering-файлы (`.kiro/steering/*`) — подгружаются сами.
2. `CONTEXT/SENSEI_MASTER_CONTEXT_v1.md` — актуальный статус.
3. `CONTEXT/PROJECT_CHANGELOG.md` — последняя запись = где мы остановились.
4. `CONTEXT/ROADMAP.md` — какой этап следующий.
5. При необходимости — `CONTEXT/Clean State (прежний чат).md` для глубокой истории.

## Правило «чекпоинта» (НЕ терять прогресс)

После КАЖДОГО значимого изменения обновлять (см. workflow.md):
- `CONTEXT/PROJECT_CHANGELOG.md` (дата, что, какие файлы, причина, откат)
- `CONTEXT/SENSEI_MASTER_CONTEXT_v1.md` (текущее состояние)
- `CONTEXT/ROADMAP.md` (если менялся план/этапы)
- синхронизировать спеки между `CODE/.kiro/specs/` и `SENSEI_PROJECT/.kiro/specs/`
