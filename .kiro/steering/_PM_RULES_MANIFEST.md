---
inclusion: always
---

# Манифест правил УП (_PM)

> Источник истины: _PM/RULES/. Этот файл — список обязательных правил УП.
> Агент при старте сессии проверяет этот манифест (см. 00-up-rules-enforcement.md).

## Версия правил: 2026-06-19c

## Активные правила УП (обязательны для всех проектов)

| # | Правило | Назначение |
|---|---------|-----------|
| 1 | 00-up-rules-enforcement.md | Принуждение к учёту правил УП при старте |
| 2 | autonomy.md | Границы автономных действий агента |
| 3 | principles.md | Принципы мышления и измеримости (до/после) |
| 4 | working-rules.md | Правила общения и разработки |
| 5 | skill-suggestions.md | Предлагать полезные навыки из надёжных источников |
| 6 | skill-search-algorithm.md | Универсальный алгоритм поиска навыков под проект |
| 7 | model-selection.md | Рекомендация модели Claude для экономии кредитов |
| 8 | entrepreneur-mindset.md | Предпринимательское мышление, roadmap, декомпозиция |
| 9 | terminal-hygiene.md | Чистота терминалов (макс. 2, закрывать) |
| 10 | project-status-protocol.md | Вести PROJECT_STATUS.md (ИСП для Сенсея) |
| 11 | never-repeat-errors.md | Журнал ошибок ERRORS_LOG.md, не повторять |
| 12 | evidence-based.md | Работа только на проверенных фактах |
| 13 | daily-cross-sync.md | Кросс-синхронизация навыков (только для УП) |
| 14 | youtube-learning.md | Изучение YouTube-видео → сводка → внедрение |
| 15 | harness-mindset.md | Harness-мышление: чини окружение, не промт |

## Как пользоваться

- Агент проекта: при старте сессии подтвердить «Правила УП v2026-06-19 учтены».
- Если какого-то правила нет в `.kiro/steering/` — запросить синхронизацию у УП.
- УП: при добавлении/изменении правила — обновить версию (дату) в этом манифесте
  и разослать манифест во все проекты.

## История версий

| Версия | Изменение |
|--------|-----------|
| 2026-06-19c | Добавлен harness-mindset, context rot в working-rules, bash-first в engineering-guidelines |
| 2026-06-19b | Добавлен youtube-learning (изучение видео по ссылке) |
| 2026-06-19 | Добавлены 00-up-rules-enforcement, skill-search-algorithm, манифест |
| 2026-06-18 | Добавлены project-status-protocol, never-repeat-errors, evidence-based |
| 2026-06-15 | Добавлены model-selection, entrepreneur-mindset |
| 2026-06-12 | Добавлен terminal-hygiene |
