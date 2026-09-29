from django.db import models


class Factura(models.Model):
    METODO_PAGO_CHOICES = [
        ('Efectivo', 'Efectivo'),
        ('Tarjeta Débito', 'Tarjeta Débito'),
        ('Tarjeta Crédito', 'Tarjeta Crédito'),
        ('Transferencia', 'Transferencia'),
        ('Otro', 'Otro'),
    ]
    cita = models.OneToOneField('SolicitudSecretaria', on_delete=models.CASCADE, related_name='factura')
    numero_factura = models.CharField(max_length=20, unique=True, editable=False)
    fecha_emision = models.DateTimeField(auto_now_add=True)
    paciente_nombre = models.CharField(max_length=200, blank=True)
    paciente_cedula = models.CharField(max_length=10, blank=True)
    especialista_nombre = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    iva = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pagada = models.BooleanField(default=False)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, blank=True, null=True, help_text="Método de pago utilizado")
    fecha_pago = models.DateTimeField(blank=True, null=True, help_text="Fecha y hora en que se registró el pago")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"

    def __str__(self):
        return f"Factura {self.numero_factura} - {self.paciente_nombre}"

    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            if not self.numero_factura:
                self.numero_factura = f"FAC-{self.id:05d}"
                super().save(update_fields=['numero_factura'])
        else:
            super().save(*args, **kwargs)
