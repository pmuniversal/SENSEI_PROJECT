@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==================================================
echo   SENSEI — Сохранение и синхронизация проекта
echo ==================================================
echo.

REM --- 1. Найти git: системный или встроенный в GitHub Desktop ---
set "GIT="
where git >nul 2>nul
if %errorlevel%==0 (
    set "GIT=git"
) else (
    for /f "delims=" %%i in ('dir /b /s "%LOCALAPPDATA%\GitHubDesktop\git.exe" 2^>nul') do (
        if not defined GIT set "GIT=%%i"
    )
)

if "%GIT%"=="" (
    echo [ОШИБКА] Git не найден. Установлен ли GitHub Desktop?
    echo.
    pause
    exit /b 1
)

echo Использую git: %GIT%
echo.

REM --- 2. Добавить все изменения ---
echo [1/3] Добавляю изменения...
"%GIT%" add -A

REM --- 3. Зафиксировать (commit). Если менять нечего — не ошибка ---
echo [2/3] Сохраняю точку (commit)...
"%GIT%" commit -m "Авто-сохранение контекста %date% %time%"
if %errorlevel% neq 0 (
    echo    Нет новых изменений для сохранения — это нормально.
)

REM --- 4. Отправить в GitHub (облако) ---
echo [3/3] Отправляю в GitHub...
"%GIT%" push
if %errorlevel% neq 0 (
    echo.
    echo [ВНИМАНИЕ] Не удалось отправить в GitHub.
    echo Проверь интернет и что ты вошёл в GitHub Desktop.
    echo.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   ГОТОВО. Всё сохранено в трёх местах:
echo   1) Ноут   2) Google Диск (само)   3) GitHub
echo ==================================================
echo.
timeout /t 4 >nul
