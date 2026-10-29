from django.contrib.auth.models import User
from django.db import models

from .paciente import Paciente


class SolicitudSecretaria(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='solicitudes_secretaria')
    especialista = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='citas_asignadas')
    fecha_cita = models.DateField()
    hora_cita = models.TimeField()
    motivo_consulta = models.TextField(blank=True, null=True)
    cuanto_cobra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Monto que se cobrará por esta consulta")
    cuanto_cobro = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Monto que se cobró por esta consulta")
    cobro_nomina = models.BooleanField(default=False)
    cubierto_por_poliza = models.BooleanField(default=False, help_text="¿Esta consulta fue cubierta por la póliza?")
    poliza = models.ForeignKey('Poliza', on_delete=models.SET_NULL, null=True, blank=True, related_name='citas', help_text="Póliza que cubre esta consulta (si aplica)")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_creadas', help_text="Usuario que creó la solicitud")
    estado = models.CharField(
        max_length=20,
        choices=[('En Espera', 'En Espera'), ('Atendido', 'Atendido'), ('Cancelado', 'Cancelado')],
        default='En Espera'
    )
    costo_consulta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Monto cobrado por esta consulta")
    monto_medico = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Porción del médico")
    monto_admin = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Porción de la administración")
    beneficiario = models.ForeignKey('Familiar', on_delete=models.SET_NULL, null=True, blank=True, related_name='citas', help_text="Familiar beneficiario de la consulta (si aplica)")

    class Meta:
        verbose_name = "Solicitud de Cita"
        verbose_name_plural = "Solicitudes de Citas"
        constraints = [
        models.UniqueConstraint(
        fields=['especialista', 'fecha_cita', 'hora_cita'],
        condition=models.Q(estado__in=['En Espera', 'Atendido']),
        name='uniq_cita_vigente_especialista_fecha_hora',
    ),
]

    def __str__(self):
        especialista = self.especialista.get_full_name() or self.especialista.username if self.especialista else "Sin asignar"
        return f"Cita para {self.paciente} con {especialista} el {self.fecha_cita} a las {self.hora_cita}"

    def calcular_costo(self):
        """Calcula el costo según tipo de paciente y tarifa vigente."""
        from decimal import Decimal

        from .tarifas import TarifaEspecialidad
        if self.cubierto_por_poliza and self.paciente.status_afiliado in ('Afiliado',):
            return (Decimal('0.00'), Decimal('0.00'), Decimal('0.00'))
        tarifa = None
        if self.especialista:
            grupos = self.especialista.groups.values_list('name', flat=True)
            for grupo in grupos:
                tarifa = TarifaEspecialidad.objects.filter(
                    especialidad__icontains=grupo, activo=True
                ).first()
                if tarifa:
                    break
        if not tarifa:
            tarifas_activas = TarifaEspecialidad.objects.filter(activo=True)
            if tarifas_activas.count() == 1:
                tarifa = tarifas_activas.first()
        costo_base = tarifa.costo_consulta if tarifa else Decimal('0.00')
        pct = tarifa.porcentaje_medico if tarifa else Decimal('50.00')
        monto_medico = (costo_base * pct / Decimal('100')).quantize(Decimal('0.01'))
        monto_admin = (costo_base - monto_medico).quantize(Decimal('0.01'))
        return (costo_base, monto_medico, monto_admin)
