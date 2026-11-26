from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models


class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    aprobado = models.BooleanField(default=False)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    aprobado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='aprobaciones')
    # GUARDAR SESION ACTIVA
    session_key = models.CharField(max_length=40, null=True, blank=True)
    # SEGUNDO FACTOR DE AUTENTICACION (OTP POR CORREO)
    autenticacion_2fa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuario"

    def __str__(self):
        return f"{self.usuario.username} - {'Aprobado' if self.aprobado else 'Pendiente'}"


class Notificacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones')
    mensaje = models.CharField(max_length=255)
    leida = models.BooleanField(default=False)
    url = models.CharField(max_length=255, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.usuario.username}: {self.mensaje[:50]}"


class LogActividad(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=255)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    objeto_id = models.IntegerField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log de Actividad"
        verbose_name_plural = "Logs de Actividad"
        ordering = ['-fecha']

    def save(self, *args, **kwargs):
        # Bitácora inmutable: solo permite inserción inicial, nunca modificación.
        if self.pk is not None and LogActividad.objects.filter(pk=self.pk).exists():
            raise ValidationError("Los registros de la bitácora son inmutables y no pueden modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Los registros de la bitácora son inmutables y no pueden eliminarse.")

    def __str__(self):
        return f"{self.fecha.strftime('%d/%m/%Y %H:%M')} - {self.usuario} - {self.accion[:60]}"
