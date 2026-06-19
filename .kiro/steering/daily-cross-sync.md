---
inclusion: always
---

# Протокол ежедневной кросс-синхронизации навыков

> Источник: _PM/RULES/daily-cross-sync.md
> УП выполняет при первом запуске за день.

## Главное правило

**Первый запуск УП за день → автоматический анализ и кросс-синхронизация навыков.**
Без запроса владельца. Молча анализирует → копирует → сообщает итог.

## Алгоритм

1. Получить список steering-файлов каждого проекта.
2. Найти файлы которые есть в одних проектах но отсутствуют в других.
3. Оценить универсальность каждого файла:
   - **Универсальные** (подходят всем): бизнес-роли, мышление, продажи, аналитика,
     операции, стратегия, протоколы работы → копировать во все проекты.
   - **Технические** (только для конкретного стека): react-native, supabase, figma,
     vps-first, telegram-bot → копировать только в технические проекты.
   - **Специфичные** (контекст одного проекта): uzbekistan-context, onboarding-pos,
     legal-compliance-uz, company-context, roadmap проекта → НЕ копировать.
4. Скопировать универсальные и подходящие технические файлы туда где их нет.
5. Git add + commit + push в каждый затронутый репо.
6. Сообщить владельцу: что скопировано, сколько файлов, в какие проекты.

## Категории файлов (справочник)

### Универсальные — копировать всем
autonomy, principles, working-rules, skill-suggestions, skill-auditor,
model-selection, entrepreneur-mindset, terminal-hygiene, project-status-protocol,
never-repeat-errors, evidence-based, output-format, structured-pm-approach,
triple-check-after-code, unit-economics, competitor-analyst, market-research,
master-sales, ceo-strategic-thinking, data-analytics, operations-excellence,
product-decisions, founder-operator, business-auditor, growth-marketing,
ltm-operations, ltm-memory-format, 00-operating-protocol

### Технические — только для проектов с кодом/SaaS
react-native, supabase, figma-source-of-truth, vps-first-development,
devops-sre, engineering-guidelines, principal-engineer, qa-tester,
release-workflow, saas-patterns, fullstack-mobile-dev, ai-integration,
ui-ux-design, telegram-bot, cfo-finance

### Специфичные — НЕ копировать в другие проекты
uzbekistan-context, legal-compliance-uz, onboarding-pos, company-context,
collection-analyst-knowledge, autonomy-trusted-commands, feature-protocol,
task-status-protocol, roadmap (проектный), 00-context-anchor, product, tech,
structure, workflow, pm-role

## Запрещено
- Копировать специфичные файлы в другие проекты.
- Перезаписывать уже существующий файл (если есть — пропустить).
- Пропускать git push после синхронизации.