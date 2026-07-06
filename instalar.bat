@echo off
title Instalador - Sistema IPP
cd /d "%~dp0"

echo ============================================
echo   Sistema IPP - Instalacion Automatica
echo ============================================
echo.

:: 1. Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado.
    echo Descarguelo de: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python detectado

:: 2. Crear entorno virtual
echo.
echo [1/5] Creando entorno virtual...
if exist venv (
    echo       El entorno virtual ya existe.
) else (
    python -m venv venv
    echo       Entorno virtual creado.
)

:: 3. Activar e instalar dependencias
echo [2/5] Instalando dependencias...
call venv\Scripts\activate.bat
pip install -r IPP1\requirements.txt
echo       Dependencias instaladas.

:: 4. Migraciones
echo [3/5] Ejecutando migraciones...
cd IPP1
python manage.py migrate
cd ..
echo       Migraciones aplicadas.

:: 5. Crear superusuario
echo [4/5] Creando superusuario...
cd IPP1
python manage.py createsuperuser
cd ..

:: 6. Iniciar servidor
echo.
echo ============================================
echo   Instalacion completada con exito
echo ============================================
echo.
echo [5/5] Iniciando servidor...
echo.
echo   Abre tu navegador en: http://127.0.0.1:8000
echo   Presiona Ctrl+C para detener el servidor
echo.
cd IPP1
python manage.py runserver

pause
