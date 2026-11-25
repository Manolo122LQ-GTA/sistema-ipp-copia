"""Comprueba la configuración de correo enviando un mensaje de prueba."""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Envía un correo de prueba con la configuración actual. '
        'Sirve para validar SMTP o el envío por HTTPS (EMAIL_API_KEY).'
    )

    def add_arguments(self, parser):
        parser.add_argument('destinatario', help='Correo de destino de la prueba')
        parser.add_argument(
            '--asunto',
            default='Prueba de correo - Sistema IPP-IUTAG',
            help='Asunto del mensaje de prueba',
        )
        parser.add_argument(
            '--mensaje',
            default=(
                'Este es un correo de prueba del Sistema IPP-IUTAG. '
                'Si lo recibes, la configuración de correo funciona.'
            ),
            help='Texto del mensaje de prueba',
        )

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND
        self.stdout.write(f'Backend: {backend}')
        self.stdout.write(f'Remitente: {settings.DEFAULT_FROM_EMAIL}')

        if 'HTTPEmailBackend' in backend:
            self.stdout.write(
                f'Proveedor HTTPS: {getattr(settings, "EMAIL_API_PROVIDER", "")}'
            )
            if not getattr(settings, 'EMAIL_API_KEY', ''):
                raise CommandError(
                    'EMAIL_API_KEY está vacía. Añádela al .env o configura SMTP.'
                )
        elif 'GmailWebAppBackend' in backend:
            self.stdout.write(
                f'Web App de Gmail: {getattr(settings, "GMAIL_WEBAPP_URL", "")}'
            )
            if not getattr(settings, 'GMAIL_WEBAPP_TOKEN', ''):
                raise CommandError(
                    'GMAIL_WEBAPP_TOKEN está vacío. Ejecuta '
                    '"manage.py configurar_gmail_webapp" y sigue los pasos.'
                )
        else:
            self.stdout.write(
                f'Servidor SMTP: {getattr(settings, "EMAIL_HOST", "")}:'
                f'{getattr(settings, "EMAIL_PORT", "")}'
            )

        try:
            enviados = send_mail(
                options['asunto'],
                options['mensaje'],
                settings.DEFAULT_FROM_EMAIL,
                [options['destinatario']],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f'No se pudo enviar el correo: {exc}') from exc

        if enviados:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Correo de prueba enviado a {options["destinatario"]}.'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('El backend no reportó ningún envío.')
            )
