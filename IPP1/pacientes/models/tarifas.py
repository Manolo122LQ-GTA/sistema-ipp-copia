from django.db import models


class TarifaEspecialidad(models.Model):
    especialidad = models.CharField(max_length=100, unique=True)
    costo_consulta = models.DecimalField(max_digits=10, decimal_places=2)
    porcentaje_medico = models.DecimalField(max_digits=5, decimal_places=2, default=50.00, help_text="Porcentaje que corresponde al médico (ej: 50.00)")
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tarifa de Especialidad"
        verbose_name_plural = "Tarifas de Especialidades"

    def __str__(self):
        return f"{self.especialidad} - ${self.costo_consulta}"
