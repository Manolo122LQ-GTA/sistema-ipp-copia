#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import ctypes

# Limpiar del entorno real de Windows las variables PG* que pueda haber
# heredado el proceso y que psycopg2 leerian con codificacion no UTF-8.
_kernel32 = ctypes.windll.kernel32

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
