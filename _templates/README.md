# _templates — скелет нового проекта

Переиспользуемая заготовка для нового направления в `KIRO_PROJECTS`.

## Что внутри `common/`
- `steering/autonomy.md`, `principles.md`, `working-rules.md` — общие (переносимые)
  правила поведения ассистента. Одинаковы во всех проектах.
- `CONTEXT/ROADMAP.md`, `PROJECT_CHANGELOG.md`, `CHECKPOINT_LATEST.md` — пустые скелеты.

## Как развернуть новый проект
1. Создать папку `KIRO_PROJECTS/<ИмяПроекта>`.
2. Скопировать `common/steering/*` → `<Проект>/.kiro/steering/`.
3. Скопировать `common/CONTEXT/*` → `<Проект>/CONTEXT/`.
4. Создать `<Проект>/.kiro/steering/00-context-anchor.md` (что за проект, роль, цель).
5. Создать `<Проект>/PROJECT_STATUS.md` (его читает Сенсей) — заполнить шапку.
6. Добавить строку проекта в `KIRO_PROJECTS/PORTFOLIO_INDEX.md`.
7. Открыть папку проекта в отдельном окне Kiro.

> Эти общие правила НЕ содержат данных конкретного проекта — только поведение.
