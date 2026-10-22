@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo               INICIANDO MEEP BOT
echo ========================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] No se encontro Python en el sistema.
    echo Asegurate de tener Python 3.10+ instalado y agregado al PATH.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [AVISO] No se encontro el archivo .env.
    echo Creando .env a partir de .env.example...
    copy .env.example .env >nul
    echo.
    echo ========================================================
    echo  IMPORTANTE:
    echo  Se ha generado el archivo .env en esta carpeta.
    echo  Por favor abrelo y coloca tu DISCORD_TOKEN.
    echo ========================================================
    echo.
    pause
    exit /b 0
)

echo Iniciando Meep...
echo Presiona Ctrl + C en esta ventana para apagar el bot.
echo.
python main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ALERTA] Meep se detuvo con codigo de error %ERRORLEVEL%.
    echo.
)

pause
