"""Cabeceras de respuesta adicionales para reducir filtrado de información."""


class ReferrerPolicyMiddleware:
    """Evita enviar la URL completa (con posibles tokens/IDs) a otros sitios."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response
