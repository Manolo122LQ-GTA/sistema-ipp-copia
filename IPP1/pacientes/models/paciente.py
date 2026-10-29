from django.db import models


class Paciente(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    cedula = models.CharField(max_length=8, unique=True)
    telefono = models.CharField(max_length=12, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_nacimiento = models.DateField()
    fecha_registro = models.DateTimeField(auto_now_add=True)
    saldo_plan_salud = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    codigo_afiliado = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text="Código único de afiliado (se genera automáticamente)")
    status_afiliado = models.CharField(
        max_length=20,
        choices=[('Afiliado', 'Afiliado'), ('Comunidad', 'Comunidad'), ('Particular', 'Particular'), ('Convenio', 'Convenio')],
        default='Comunidad'
    )
    categoria_afiliado = models.CharField(
        max_length=20,
        choices=[('Docente', 'Docente'), ('Jubilado', 'Jubilado'), ('Beneficiario', 'Beneficiario'), ('Otro', 'Otro')],
        default='Otro',
        help_text="Categoría específica del afiliado (Docente, Jubilado, Beneficiario, Otro)"
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.cedula})"

    def save(self, *args, **kwargs):
        if self.cedula:                          
            self.cedula = ''.join(c for c in str(self.cedula) if c.isdigit())
        if not self.codigo_afiliado:             
            cedula_limpia = ''.join(c for c in str(self.cedula) if c.isdigit())
            self.codigo_afiliado = f"IPP-{cedula_limpia}"
        super().save(*args, **kwargs)
