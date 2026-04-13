@echo off
chcp 65001 >nul
echo ========================================
echo  Platformer Vertical Slice
echo ========================================
echo.

REM Obtener la ruta del directorio actual
set PROJECT_DIR=%~dp0

REM Cambiar al directorio del motor (padre del proyecto)
cd /d "%PROJECT_DIR%\..\.."

echo 📂 Proyecto: %PROJECT_DIR%
echo 🎮 Iniciando motor...
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado
    echo    Instala Python desde https://python.org
    pause
    exit /b 1
)

REM Ejecutar el motor con este proyecto
python main.py --project "%PROJECT_DIR%"

if errorlevel 1 (
    echo.
    echo ❌ Error al ejecutar
    pause
    exit /b 1
)
