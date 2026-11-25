#!/usr/bin/env python
import os, sys, json

# Set up Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'IPP1.settings'
import django
django.setup()

from django.core.mail import send_mail

result = send_mail(
    'Test Resend IPP',
    'Cuerpo de prueba - correo de Resend con text/html',
    'IPP - IUTAG <onboarding@resend.dev>',
    ['irving.coello@gmail.com'],
    fail_silently=False,
)
print('Resultado send_mail:', result)