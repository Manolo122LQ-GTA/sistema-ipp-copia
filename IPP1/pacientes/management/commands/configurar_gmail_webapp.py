"""Genera el token y muestra el código del Web App de Gmail."""

import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Muestra el código de Google Apps Script y el token para enviar por '
        'Gmail usando HTTPS, sin depender de los puertos SMTP.'
    )

    def handle(self, *args, **options):
        token = (
            getattr(settings, 'GMAIL_WEBAPP_TOKEN', '').strip()
            or secrets.token_urlsafe(32)
        )
        ruta = Path(settings.BASE_DIR) / 'docs' / 'gmail_webapp.gs'
        if not ruta.exists():
            raise CommandError(f'No se encontró el archivo {ruta}')

        codigo = ruta.read_text(encoding='utf-8').replace('__TOKEN__', token)

        self.stdout.write(self.style.SUCCESS('Token para GMAIL_WEBAPP_TOKEN:'))
        self.stdout.write(token)
        self.stdout.write('')
        self.stdout.write('Código para pegar en https://script.google.com (Code.gs):')
        self.stdout.write('=' * 70)
        self.stdout.write(codigo)
        self.stdout.write('=' * 70)
        self.stdout.write('')
        self.stdout.write('Pasos:')
        self.stdout.write('1. Crea un proyecto en https://script.google.com con la cuenta de Gmail.')
        self.stdout.write('2. Pega el código anterior en Code.gs.')
        self.stdout.write('3. Implementar > Nueva implementación > Aplicación web.')
        self.stdout.write('   Ejecutar como: Yo. Quién tiene acceso: Cualquier persona.')
        self.stdout.write('4. Copia la URL que termina en /exec.')
        self.stdout.write('5. Añade al .env:')
        self.stdout.write('   GMAIL_WEBAPP_URL=https://script.google.com/macros/s/.../exec')
        self.stdout.write(f'   GMAIL_WEBAPP_TOKEN={token}')
        self.stdout.write('')
        self.stdout.write('Prueba el envío con:')
        self.stdout.write(
            '  .\\venv\\Scripts\\python.exe manage.py enviar_correo_prueba '
            'coelloirving2026@gmail.com'
        )
