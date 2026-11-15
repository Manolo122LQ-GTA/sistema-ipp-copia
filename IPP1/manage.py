#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import ctypes

# Forzar variables de conexión a DB con valores UTF-8 puros en el entorno REAL de Windows
# Usar SetEnvironmentVariableW de Windows API para que libpq/psycopg2 lo vea
_kernel32 = ctypes.windll.kernel32

_db_clean = {
    'DB_NAME': 'IPPBD',
    'DB_USER': 'postgres',
    'DB_PASSWORD': '1234',
    'DB_HOST': 'localhost',
    'DB_PORT': '5432',
}
for _k, _v in _db_clean.items():
    _kernel32.SetEnvironmentVariableW(_k, _v)
    os.environ[_k] = _v

# Eliminar todas las variables PG* del entorno real de Windows
for _key in list(os.environ.keys()):
    if _key.startswith('PG'):
        try:
            _kernel32.SetEnvironmentVariableW(_key, None)
        except OSError:
            pass
        try:
            del os.environ[_key]
        except KeyError:
            pass


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'IPP1.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
