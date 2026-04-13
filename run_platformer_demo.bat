@echo off
chcp 65001 >nul
echo ========================================
echo  MotorVideojuegosIA - Platformer Demo
echo ========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado en el PATH
    echo    Por favor instala Python 3.8+ desde https://python.org
    pause
    exit /b 1
)

echo ✅ Python encontrado
python --version

REM Verificar dependencias
echo.
echo Verificando dependencias...
python -c "import pyray" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Instalando dependencias...
    pip install pyray
)

echo ✅ Dependencias OK

REM Ejecutar el juego
echo.
echo 🎮 Iniciando Platformer Vertical Slice...
echo    Controles: A/D o Flechas para mover, SPACE para saltar
echo.

python main.py --level levels/platformer_vertical_slice.json

if errorlevel 1 (
    echo.
    echo ❌ Error al ejecutar el juego
    pause
    exit /b 1
)

echo.
echo 👋 Gracias por jugar!
pause
