from .models import Notificacion


def notificaciones(request):
    ctx = {
        'notificaciones_no_leidas': [],
        'notificaciones_count': 0,
    }
    if request.user.is_authenticated:
        no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False)
        ctx['notificaciones_no_leidas'] = no_leidas[:5]
        ctx['notificaciones_count'] = no_leidas.count()
    return ctx
