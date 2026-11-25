"""Backend de correo por HTTPS.

Muchas redes (incluida la de este entorno) bloquean los puertos SMTP
tradicionales (25, 465 y 587), pero permiten HTTPS. Este backend envía el
correo usando la API HTTP de un proveedor, sin abrir conexiones SMTP.

Proveedores soportados:
    - brevo     https://api.brevo.com/v3/smtp/email
    - resend    https://api.resend.com/emails
    - sendgrid  https://api.sendgrid.com/v3/mail/send

Configuración en .env:
    EMAIL_API_PROVIDER=brevo
    EMAIL_API_KEY=tu-clave-api
    EMAIL_API_FROM=remitente-verificado@ejemplo.com
    EMAIL_API_TIMEOUT=15
"""

import json
import logging

import requests

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class HTTPEmailBackend(BaseEmailBackend):
    """Envía correos con la API HTTPS de Brevo, Resend o SendGrid."""

    endpoints = {
        'brevo': 'https://api.brevo.com/v3/smtp/email',
        'resend': 'https://api.resend.com/emails',
        'sendgrid': 'https://api.sendgrid.com/v3/mail/send',
    }

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.provider = getattr(settings, 'EMAIL_API_PROVIDER', 'brevo').strip().lower()
        self.api_key = getattr(settings, 'EMAIL_API_KEY', '').strip()
        self.timeout = int(getattr(settings, 'EMAIL_API_TIMEOUT', 15))

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise ValueError(
                'EMAIL_API_KEY no está configurada. Añádela al .env para enviar '
                'correos por HTTPS.'
            )
        if self.provider not in self.endpoints:
            if self.fail_silently:
                return 0
            raise ValueError(
                f'Proveedor de correo no soportado: {self.provider!r}. '
                f'Usa uno de: {", ".join(sorted(self.endpoints))}.'
            )

        enviados = 0
        for mensaje in email_messages:
            try:
                self._post(self._payload(mensaje))
                enviados += 1
            except Exception:
                logger.exception(
                    'Error enviando correo por %s a %s',
                    self.provider,
                    ', '.join(mensaje.to),
                )
                if not self.fail_silently:
                    raise
        return enviados

    def _post(self, payload):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'IPP-System/1.0',
        }
        if self.provider == 'brevo':
            headers['api-key'] = self.api_key
        else:
            headers['Authorization'] = f'Bearer {self.api_key}'

        url = self.endpoints[self.provider]
        respuesta = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )

        if respuesta.status_code >= 300:
            raise RuntimeError(
                f'{self.provider} respondió {respuesta.status_code}: {respuesta.text}'
            )

        return respuesta.text

    def _auth_headers(self):
        if self.provider == 'brevo':
            return {'api-key': self.api_key}
        return {'Authorization': f'Bearer {self.api_key}'}

    def _payload(self, mensaje):
        remitente = mensaje.from_email or settings.DEFAULT_FROM_EMAIL
        texto = mensaje.body or ''
        html = next(
            (
                contenido
                for contenido, tipo in getattr(mensaje, 'alternatives', [])
                if tipo == 'text/html'
            ),
            None,
        )
        adjuntos = self._adjuntos(mensaje)

        if self.provider == 'brevo':
            return self._payload_brevo(mensaje, remitente, texto, html, adjuntos)
        if self.provider == 'resend':
            return self._payload_resend(mensaje, remitente, texto, html, adjuntos)
        return self._payload_sendgrid(mensaje, remitente, texto, html, adjuntos)

    def _payload_brevo(self, mensaje, remitente, texto, html, adjuntos):
        nombre, correo = parseaddr(remitente)
        payload = {
            'sender': {'email': correo, **({'name': nombre} if nombre else {})},
            'to': self._destinatarios_brevo(mensaje.to),
            'subject': mensaje.subject,
        }
        if mensaje.cc:
            payload['cc'] = self._destinatarios_brevo(mensaje.cc)
        if mensaje.bcc:
            payload['bcc'] = self._destinatarios_brevo(mensaje.bcc)
        if mensaje.reply_to:
            nombre_r, correo_r = parseaddr(mensaje.reply_to[0])
            payload['replyTo'] = {
                'email': correo_r,
                **({'name': nombre_r} if nombre_r else {}),
            }
        if texto:
            payload['textContent'] = texto
        if html:
            payload['htmlContent'] = html
        if adjuntos:
            payload['attachment'] = [
                {'content': contenido, 'name': nombre}
                for nombre, contenido, _tipo in adjuntos
            ]
        return payload

    def _payload_resend(self, mensaje, remitente, texto, html, adjuntos):
        payload = {
            'from': remitente,
            'to': list(mensaje.to),
            'subject': mensaje.subject,
        }
        if texto:
            payload['text'] = texto
        if html:
            payload['html'] = html
        # Resend requiere al menos un campo text o html con contenido
        if 'text' not in payload and 'html' not in payload:
            payload['text'] = ''
        if mensaje.cc:
            payload['cc'] = list(mensaje.cc)
        if mensaje.bcc:
            payload['bcc'] = list(mensaje.bcc)
        if mensaje.reply_to:
            payload['reply_to'] = list(mensaje.reply_to)
        if adjuntos:
            payload['attachments'] = [
                {'filename': nombre, 'content': contenido}
                for nombre, contenido, _tipo in adjuntos
            ]
        return payload

    def _payload_sendgrid(self, mensaje, remitente, texto, html, adjuntos):
        nombre, correo = parseaddr(remitente)
        personalizacion = {
            'to': self._destinatarios_sendgrid(mensaje.to),
        }
        if mensaje.cc:
            personalizacion['cc'] = self._destinatarios_sendgrid(mensaje.cc)
        if mensaje.bcc:
            personalizacion['bcc'] = self._destinatarios_sendgrid(mensaje.bcc)
        payload = {
            'personalizations': [personalizacion],
            'from': {'email': correo, **({'name': nombre} if nombre else {})},
            'subject': mensaje.subject,
            'content': [],
        }
        if mensaje.reply_to:
            nombre_r, correo_r = parseaddr(mensaje.reply_to[0])
            payload['reply_to'] = {
                'email': correo_r,
                **({'name': nombre_r} if nombre_r else {}),
            }
        if texto:
            payload['content'].append({'type': 'text/plain', 'value': texto})
        if html:
            payload['content'].append({'type': 'text/html', 'value': html})
        if not payload['content']:
            payload['content'].append({'type': 'text/plain', 'value': ''})
        if adjuntos:
            payload['attachments'] = [
                {
                    'content': contenido,
                    'filename': nombre,
                    'type': tipo or 'application/octet-stream',
                    'disposition': 'attachment',
                }
                for nombre, contenido, tipo in adjuntos
            ]
        return payload

    @staticmethod
    def _destinatarios_brevo(direcciones):
        resultado = []
        for direccion in direcciones:
            nombre, correo = parseaddr(direccion)
            resultado.append({'email': correo, **({'name': nombre} if nombre else {})})
        return resultado

    @staticmethod
    def _destinatarios_sendgrid(direcciones):
        resultado = []
        for direccion in direcciones:
            nombre, correo = parseaddr(direccion)
            resultado.append({'email': correo, **({'name': nombre} if nombre else {})})
        return resultado

    @staticmethod
    def _adjuntos(mensaje):
        adjuntos = []
        for nombre, contenido, tipo in mensaje.attachments:
            if isinstance(contenido, str):
                contenido = contenido.encode('utf-8')
            adjuntos.append((nombre, __import__('base64').b64encode(contenido).decode('ascii'), tipo))
        return adjuntos