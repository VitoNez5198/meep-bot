@echo off
chcp 65001 > nul
title Meep Bot - Companion Privado (LoL y Música)

echo ========================================================
echo               INICIANDO MEEP BOT
echo ========================================================
echo.

cd /d "%~dp0"

REM Verificar Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] No se encontró Python en el sistema.
    echo Asegúrate de tener Python 3.10+ instalado y agregado al PATH.
    echo.
    pause
    exit /b 1
)

REM Verificar si existe el archivo .env
if not exist ".env" (
    echo [AVISO] No se encontró el archivo .env.
    echo Creando .env a partir de .env.example...
    copy .env.example .env > nul
    echo.
    echo ========================================================
    echo  ¡IMPORTANTE!
    echo  Se ha generado el archivo .env en esta carpeta.
    echo  Por favor ábrelo con el Bloc de notas y coloca tu
    echo  DISCORD_TOKEN antes de continuar.
    echo ========================================================
    echo.
    pause
    exit /b 0
)

echo Iniciando Meep...
echo Presiona Ctrl + C en esta ventana para apagar el bot.
echo.
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ALERTA] Meep se detuvo con un código de error (%errorlevel%).
    echo.
)

pause
