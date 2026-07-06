SISTEMA IPP - INSTALACION RAPIDA
==================================

REQUISITOS:
- Python 3.10 o superior (descargar de https://www.python.org/downloads/)
  IMPORTANTE: Al instalar Python, marcar "Add Python to PATH"

INSTALACION (2 formas):

--- OPCION 1: INSTALACION AUTOMATICA (Recomendada) ---
Haz doble clic en "instalar.bat" y sigue los pasos.
El script creara el entorno virtual, instalara todo,
ejecutara migraciones, creara el superusuario e iniciara el servidor.

--- OPCION 2: INSTALACION MANUAL ---
Abre una terminal en esta carpeta y ejecuta:

  1. python -m venv venv
  2. venv\Scripts\activate
  3. pip install -r IPP1\requirements.txt
  4. cd IPP1
  5. python manage.py migrate
  6. python manage.py createsuperuser
  7. python manage.py runserver

Luego abre http://127.0.0.1:8000 en el navegador.

DEPENDENCIAS INSTALADAS:
- Django (framework web)
- openpyxl (exportar a Excel)
- tzdata (husos horarios)
