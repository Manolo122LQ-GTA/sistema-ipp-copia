# SISTEMA INTEGRADO DE REGISTRO DE PACIENTES IPP-IUTAG

Sistema integrado de registro de pacientes que ayuda a la comunidad del IPP-IUTAG a optimizar su área de trabajo.

* Versión actual: 1.70_1
* Tecnología: Django 6.0.4 · PostgreSQL · Python 3.14 · Bootstrap 5 (offline con WhiteNoise)
* Rama: `main`

## Requisitos

* Python 3.14
* PostgreSQL 18
* Virtualenv en `venv/`

## Configuración

1. Clonar el repositorio y crear el virtualenv:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r IPP1\requirements.txt
   ```

2. Crear el archivo `.env` en la carpeta del proyecto (no está versionado):

   ```env
   SECRET_KEY=<clave_secreta>
   ALLOWED_HOSTS=localhost,127.0.0.1
   DB_NAME=IPPBD
   DB_USER=postgres
   DB_PASSWORD=<password>
   DB_HOST=localhost
   DB_PORT=5432
   EMAIL_HOST_USER=
   EMAIL_HOST_PASSWORD=
   # Orígenes permitidos para POST (requerido si se publica con HTTPS/dominio)
   CSRF_TRUSTED_ORIGINS=https://dominio.com,https://www.dominio.com
   ```

3. Ejecutar migraciones y el servidor:

   ```powershell
   .\venv\Scripts\python.exe manage.py migrate
   .\venv\Scripts\python.exe manage.py runserver
   ```

4. `SECRET_KEY` es obligatoria: sin ella el sistema no arranca (evita claves comprometidas en el repositorio).

## Roles del sistema

* Superuser
* Administracion
* Secretaria
* Medico
* Odontologo
* Laboratorio
* Especialista

Los usuarios nuevos se registran y quedan pendientes de aprobación por un administrador antes de poder ingresar.

## Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test
```

## Notas

* Los registros de pacientes no se eliminan: se desactivan.
* Bloqueo por intentos de login fallidos (django-axes, 5 intentos) con recuperación de acceso.
* Los estáticos se sirven con WhiteNoise (`staticfiles/` es salida de `collectstatic`).
