from django.db import models


class Medicamento(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_stock = models.IntegerField(default=0)
    lote = models.CharField(max_length=100, blank=True, null=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Medicamento"
        verbose_name_plural = "Medicamentos"
        unique_together = [('nombre', 'lote')]

    def __str__(self):
        return f"{self.nombre} (stock: {self.cantidad_stock})"


class Receta(models.Model):
    cita = models.ForeignKey('SolicitudSecretaria', on_delete=models.CASCADE, related_name='recetas')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.SET_NULL, null=True, blank=True)
    examen = models.ForeignKey('ExamenLaboratorio', on_delete=models.SET_NULL, null=True, blank=True, help_text="Examen de laboratorio recetado (opcional)")
    cantidad = models.IntegerField(default=1, help_text="Cantidad recetada")
    dosis = models.CharField(max_length=200, help_text="Ej: 1 tableta cada 8 horas")
    duracion = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: 7 días")
    indicaciones = models.TextField(blank=True, null=True, help_text="Instrucciones adicionales")
    fecha_prescrita = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Receta"
        verbose_name_plural = "Recetas"

    def __str__(self):
        med = self.medicamento.nombre if self.medicamento else (self.examen.nombre if self.examen else "N/A")
        return f"Receta: {med} para {self.cita.paciente} ({self.cita.fecha_cita})"
