from decimal import Decimal

from django.db import models

from .paciente import Paciente


class ExamenLaboratorio(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Examen de Laboratorio"
        verbose_name_plural = "Exámenes de Laboratorio"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} - ${self.costo}"

    @property
    def costo_afiliado(self):
        return (self.costo * Decimal('0.80')).quantize(Decimal('0.01'))


class SolicitudLaboratorio(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='solicitudes_laboratorio')
    examen = models.ForeignKey(ExamenLaboratorio, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes')
    prueba_laboratorio = models.CharField(max_length=255)
    fecha_solicitud = models.DateField()
    resultado = models.TextField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bioanalista = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=[('Pendiente', 'Pendiente'), ('Procesado', 'Procesado')],
        default='Pendiente'
    )
    fecha_procesamiento = models.DateTimeField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Solicitud de Laboratorio"
        verbose_name_plural = "Solicitudes de Laboratorio"

    def __str__(self):
        return f"Laboratorio para {self.paciente} ({self.prueba_laboratorio}) el {self.fecha_solicitud}"
