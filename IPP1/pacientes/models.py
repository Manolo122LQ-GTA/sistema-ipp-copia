from django.db import models
from django.contrib.auth.models import User

# PERFIL DE USUARIO
class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    aprobado = models.BooleanField(default=False)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    aprobado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='aprobaciones')

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuario"

    def __str__(self):
        return f"{self.usuario.username} - {'Aprobado' if self.aprobado else 'Pendiente'}"

# PACIENTE
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
        choices=[('Afiliado', 'Afiliado'), ('Comunidad', 'Comunidad'), ('Particular', 'Particular')],
        default='Comunidad'
    )
    categoria_afiliado = models.CharField(
        max_length=20,
        choices=[('Docente', 'Docente'), ('Jubilado', 'Jubilado'), ('Beneficiario', 'Beneficiario'), ('Otro', 'Otro')],
        default='Otro',
        help_text="Categoría específica del afiliado (Docente, Jubilado, Beneficiario, Otro)"
    )
    activo = models.BooleanField(default=True)
    # usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='paciente', help_text="Usuario vinculado para acceso al portal")

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.cedula})"

    def save(self, *args, **kwargs):
        if not self.codigo_afiliado:
            cedula_limpia = ''.join(c for c in str(self.cedula) if c.isdigit())
            self.codigo_afiliado = f"IPP-{cedula_limpia}"
        super().save(*args, **kwargs)

# SOLICITUD-SECRETARIA
class SolicitudSecretaria(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='solicitudes_secretaria')
    # Asumimos que 'especialista' es un usuario del sistema (ej. un médico)
    especialista = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='citas_asignadas')
    fecha_cita = models.DateField()
    hora_cita = models.TimeField()
    motivo_consulta = models.TextField(blank=True, null=True)
    cobro_nomina = models.BooleanField(default=False)
    cubierto_por_poliza = models.BooleanField(default=False, help_text="¿Esta consulta fue cubierta por la póliza?")
    poliza = models.ForeignKey('Poliza', on_delete=models.SET_NULL, null=True, blank=True, related_name='citas', help_text="Póliza que cubre esta consulta (si aplica)")
    fecha_creacion = models.DateTimeField(auto_now_add=True) # Campo para registrar cuándo se creó la solicitud
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

    def __str__(self):
        especialista = self.especialista.get_full_name() or self.especialista.username if self.especialista else "Sin asignar"
        return f"Cita para {self.paciente} con {especialista} el {self.fecha_cita} a las {self.hora_cita}"

    def calcular_costo(self):
        """Calcula el costo según tipo de paciente y tarifa vigente."""
        from decimal import Decimal
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
            tarifa = TarifaEspecialidad.objects.filter(activo=True).first()
        costo_base = tarifa.costo_consulta if tarifa else Decimal('0.00')
        pct = tarifa.porcentaje_medico if tarifa else Decimal('50.00')
        monto_medico = (costo_base * pct / Decimal('100')).quantize(Decimal('0.01'))
        monto_admin = (costo_base - monto_medico).quantize(Decimal('0.01'))
        return (costo_base, monto_medico, monto_admin)

# EXAMEN DE LABORATORIO (Catálogo)
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
        from decimal import Decimal
        return (self.costo * Decimal('0.80')).quantize(Decimal('0.01'))


# SOLICITUD LABORATORIO
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
    fecha_creacion = models.DateTimeField(auto_now_add=True) # Campo para registrar cuándo se creó la solicitud

    class Meta:
        verbose_name = "Solicitud de Laboratorio"
        verbose_name_plural = "Solicitudes de Laboratorio"

    def __str__(self):
        return f"Laboratorio para {self.paciente} ({self.prueba_laboratorio}) el {self.fecha_solicitud}"


# PLAN SALUD
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

# POLIZA
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
        from django.utils import timezone
        ano_actual = timezone.now().year
        return self.citas.filter(
            fecha_cita__year=ano_actual,
            cubierto_por_poliza=True
        ).exclude(estado='Cancelado').count()

    def consultas_restantes(self):
        if not self.plan or self.plan.consultas_maximas_anuales == 0:
            return None
        return max(0, self.plan.consultas_maximas_anuales - self.consultas_usadas_anuales())

# GASTO PACIENTE
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

# FAMILIAR
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

# FACTURA
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
        super().save(*args, **kwargs)
        if not self.numero_factura:
            self.numero_factura = f"FAC-{self.id:05d}"
            super().save(update_fields=['numero_factura'])

# TARIFAS ESPECIALISTAS
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

# MEDICAMENTOS
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

# RECETA
class Receta(models.Model):
    cita = models.ForeignKey('SolicitudSecretaria', on_delete=models.CASCADE, related_name='recetas')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.SET_NULL, null=True, blank=True)
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
        med = self.medicamento.nombre if self.medicamento else "N/A"
        return f"Receta: {med} para {self.cita.paciente} ({self.cita.fecha_cita})"

# NOTIFICACION
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

# LOG ACTIVIDAD
class LogActividad(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=255)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    objeto_id = models.IntegerField(blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log de Actividad"
        verbose_name_plural = "Logs de Actividad"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.fecha.strftime('%d/%m/%Y %H:%M')} - {self.usuario} - {self.accion[:60]}"