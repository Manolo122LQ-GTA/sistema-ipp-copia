import os
from io import StringIO
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


def generar_respaldo_json():
    """Genera un respaldo JSON completo en BASE_DIR/respaldos y devuelve (ruta, contenido_bytes)."""
    respaldo_dir = settings.BASE_DIR / 'respaldos'
    os.makedirs(respaldo_dir, exist_ok=True)
    marca = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    nombre = f'respaldo_ipp_{marca}.json'
    ruta = respaldo_dir / nombre

    buffer = StringIO()
    call_command(
        'dumpdata',
        exclude=['contenttypes', 'sessions', 'admin.logentry'],
        natural_foreign=True,
        natural_primary=True,
        indent=2,
        stdout=buffer,
    )
    contenido = buffer.getvalue().encode('utf-8')
    with open(ruta, 'wb') as archivo:
        archivo.write(contenido)
    return ruta, contenido


class Command(BaseCommand):
    help = 'Genera una copia de seguridad en JSON de la base de datos en /respaldos/.'

    def handle(self, *args, **options):
        ruta, _ = generar_respaldo_json()
        self.stdout.write(self.style.SUCCESS(f'Respaldo generado exitosamente: {ruta}'))
