"""Comprobaciones de las paginas de error del sistema."""

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from IPP1.urls import handler400, handler403, handler404, handler500


class PaginasErrorTest(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_templates_comparten_el_diseno(self):
        casos = {
            'ipp1/errores/400.html': ('400', 'Solicitud no válida'),
            'ipp1/errores/403.html': ('403', 'Acceso denegado'),
            'ipp1/errores/404.html': ('404', 'Página no encontrada'),
            'ipp1/errores/500.html': ('500', 'Error del servidor'),
        }
        for plantilla, (codigo, titulo) in casos.items():
            with self.subTest(plantilla=plantilla):
                html = render_to_string(plantilla)
                self.assertIn(codigo, html)
                self.assertIn(titulo, html)
                self.assertIn('error-shell', html)
                self.assertIn('/css/errores', html)

    def test_handlers_devuelven_el_estado_correcto(self):
        request = self.rf.get('/')
        request.user = AnonymousUser()
        casos = [
            (handler400, 400, 'Solicitud no válida'),
            (handler403, 403, 'Acceso denegado'),
            (handler404, 404, 'Página no encontrada'),
        ]
        for handler, estado, titulo in casos:
            with self.subTest(handler=handler.__name__):
                respuesta = handler(request, Exception('prueba'))
                self.assertEqual(respuesta.status_code, estado)
                self.assertContains(respuesta, titulo, status_code=estado)

        respuesta = handler500(request)
        self.assertEqual(respuesta.status_code, 500)
        self.assertContains(respuesta, 'Error del servidor', status_code=500)

    def test_ruta_inexistente_usa_la_pagina_404(self):
        respuesta = self.client.get('/ruta-que-no-existe-ipp/')
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, 'Página no encontrada', status_code=404)
