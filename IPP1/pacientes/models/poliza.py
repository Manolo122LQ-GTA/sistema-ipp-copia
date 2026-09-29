from django.db import models
from django.utils import timezone

from .paciente import Paciente


class PlanSalud(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    costo_mensual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cobertura = models.TextField(blank=True, null=True, help_text="Servicios cubiertos por el plan")
    consultas_maximas_anuales = models.IntegerField(default=4, help_text="Número máximo de consultas cubiertas por año (0 = ilimitado)")

    class Meta:
        verbose_name = "Plan de Salud"
        verbose_name_plural = "Planes de Salud"

    def __str__(self):
        return f"{self.nombre} - ${self.costo_mensual}/mes ({self.consultas_maximas_anuales} consultas/año)"


class Poliza(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='polizas')
    plan = models.ForeignKey(PlanSalud, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')],
        default='Activo'
    )
    saldo_restante = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    cuota_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Póliza"
        verbose_name_plural = "Pólizas"

    def __str__(self):
        return f"Póliza {self.paciente.nombre} {self.paciente.apellido} - {self.plan or 'Sin Plan'}"

    def consultas_usadas_anuales(self):
        ano_actual = timezone.localdate().year
        return self.citas.filter(
            fecha_cita__year=ano_actual,
            cubierto_por_poliza=True
        ).exclude(estado='Cancelado').count()

    def consultas_restantes(self):
        if not self.plan or self.plan.consultas_maximas_anuales == 0:
            return None
        return max(0, self.plan.consultas_maximas_anuales - self.consultas_usadas_anuales())


class GastoPaciente(models.Model):
    poliza = models.ForeignKey(Poliza, on_delete=models.CASCADE, related_name='gastos')
    concepto = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField()
    factura = models.CharField(max_length=100, blank=True, null=True, help_text="Número de factura o recibo")
    beneficiario = models.ForeignKey('Familiar', on_delete=models.SET_NULL, null=True, blank=True, related_name='gastos', help_text="Familiar específico al que se atribuye este gasto (si aplica)")

    class Meta:
        verbose_name = "Gasto del Paciente"
        verbose_name_plural = "Gastos del Paciente"

    def __str__(self):
        return f"{self.concepto} - ${self.monto} ({self.poliza.paciente})"


class Familiar(models.Model):
    poliza = models.ForeignKey(Poliza, on_delete=models.CASCADE, related_name='familiares')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    cedula = models.CharField(max_length=10)
    parentesco = models.CharField(max_length=50, help_text="Ej: Hijo, Cónyuge, Padre")
    fecha_nacimiento = models.DateField()

    class Meta:
        verbose_name = "Familiar"
        verbose_name_plural = "Familiares"

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.parentesco})"
