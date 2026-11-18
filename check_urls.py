"""Comprueba que todos los {% url 'nombre' %} usados en las plantillas existan.

No intenta resolver los argumentos (serian variables del template y habria que
ejecutar la vista para conocerlas): solo verifica que el nombre de la ruta este
registrado. Asi se evitan los falsos positivos de "Reverse for 'x' with no
arguments not found" cuando la ruta si existe pero exige un parametro.
"""
import os
import re
import sys

import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'IPP1'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'IPP1.settings')
django.setup()

from django.urls import NoReverseMatch, get_resolver, reverse  # noqa: E402

template_dir = os.path.join(os.path.dirname(__file__), 'IPP1', 'template')

url_pattern = re.compile(
    r"{%\s*url\s+['\"]([^'\"]+)['\"]\s*([^%]*?)\s*%}",
    re.DOTALL,
)

nombres_registrados = set(get_resolver().reverse_dict.keys())


def ruta_existe(nombre):
    if nombre in nombres_registrados:
        return True
    try:
        reverse(nombre)
        return True
    except NoReverseMatch:
        return False


issues = []
for root, _dirs, files in os.walk(template_dir):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        for m in url_pattern.finditer(content):
            name = m.group(1)
            if not ruta_existe(name):
                issues.append((os.path.relpath(path, template_dir), name))

if issues:
    print('Rutas usadas en templates que NO existen:')
    for path, name in issues:
        print(f'  {path}: {name}')
    sys.exit(1)

print('OK: todas las rutas usadas en las plantillas existen.')