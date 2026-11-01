from django.contrib import admin
from .models import PerfilUsuario, Paciente, SolicitudSecretaria, SolicitudLaboratorio, ExamenLaboratorio, PlanSalud, Poliza, GastoPaciente, Familiar, TarifaEspecialidad, Medicamento, Receta, Notificacion, LogActividad, Factura

# Register your models here.

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'aprobado', 'fecha_registro', 'fecha_aprobacion', 'aprobado_por')
    list_filter = ('aprobado',)
    search_fields = ('usuario__username',)

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('codigo_afiliado', 'cedula', 'nombre', 'apellido', 'status_afiliado', 'telefono', 'activo')
    search_fields = ('cedula', 'apellido', 'codigo_afiliado')
    list_filter = ('status_afiliado', 'activo')

@admin.register(SolicitudSecretaria)
class SolicitudSecretariaAdmin(admin.ModelAdmin):
    list_display = ('id', 'paciente', 'especialista', 'fecha_cita', 'hora_cita', 'cubierto_por_poliza', 'costo_consulta')
    list_filter = ('fecha_cita', 'especialista', 'cubierto_por_poliza')
    search_fields = ('paciente__cedula', 'paciente__apellido')

@admin.register(SolicitudLaboratorio)
class SolicitudLaboratorioAdmin(admin.ModelAdmin):
    list_display = ('id', 'paciente', 'prueba_laboratorio', 'fecha_solicitud')
    list_filter = ('fecha_solicitud',)
    search_fields = ('paciente__cedula', 'paciente__apellido')

@admin.register(PlanSalud)
class PlanSaludAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'costo_mensual', 'servicios_maximos_anuales')

@admin.register(Poliza)
class PolizaAdmin(admin.ModelAdmin):
    list_display = ('id', 'paciente', 'plan', 'estado', 'saldo_restante', 'consultas_restantes')
    list_filter = ('estado', 'plan')
    search_fields = ('paciente__cedula', 'paciente__apellido')

    def consultas_restantes(self, obj):
        r = obj.consultas_restantes()
        return r if r is not None else 'Ilimitado'
    consultas_restantes.short_description = 'Consultas restantes'

@admin.register(GastoPaciente)
class GastoPacienteAdmin(admin.ModelAdmin):
    list_display = ('concepto', 'monto', 'fecha', 'poliza')
    list_filter = ('fecha',)

@admin.register(Familiar)
class FamiliarAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'cedula', 'parentesco', 'poliza')
    search_fields = ('cedula',)

@admin.register(TarifaEspecialidad)
class TarifaEspecialidadAdmin(admin.ModelAdmin):
    list_display = ('especialidad', 'costo_consulta', 'porcentaje_medico', 'activo')
    list_filter = ('activo',)
    search_fields = ('especialidad',)

@admin.register(Medicamento)
class MedicamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad_stock', 'precio', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'lote')

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'mensaje', 'leida', 'fecha_creacion')
    list_filter = ('leida', 'fecha_creacion')
    search_fields = ('usuario__username', 'mensaje')

@admin.register(LogActividad)
class LogActividadAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'accion', 'modelo')
    list_filter = ('fecha', 'modelo')
    search_fields = ('usuario__username', 'accion', 'detalle')
    date_hierarchy = 'fecha'

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero_factura', 'paciente_nombre', 'total', 'pagada', 'fecha_emision')
    list_filter = ('pagada', 'fecha_emision')
    search_fields = ('numero_factura', 'paciente_nombre', 'paciente_cedula')

@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ('id', 'cita', 'medicamento', 'cantidad', 'dosis', 'fecha_prescrita')
    list_filter = ('fecha_prescrita',)
    search_fields = ('cita__paciente__nombre', 'medicamento__nombre')

@admin.register(ExamenLaboratorio)
class ExamenLaboratorioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'costo', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)