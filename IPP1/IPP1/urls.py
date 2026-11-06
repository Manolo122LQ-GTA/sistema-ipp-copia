from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from pacientes import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView


def handler404(request, exception):
    return render(request, 'ipp1/errores/404.html', status=404)


def handler403(request, exception):
    return render(request, 'ipp1/errores/403.html', status=403)


def handler500(request):
    return render(request, 'ipp1/errores/500.html', status=500)

urlpatterns = [

    # Administrador
    path('admin/', admin.site.urls),

    # El login (Usamos tu vista personalizada de views.py)
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # El registro :v
    path('registro/', views.registro, name='registro'),

    # Aprobación pendiente
    path('pendiente-aprobacion/', views.pendiente_aprobacion, name='pendiente_aprobacion'),

    # Secretaria
    path('secretaria/inicio/', views.secretaria, name='secretaria'),
    path('secretaria/registrar_paciente/', views.registrar_paciente, name='registrar_paciente'),
    path('secretaria/mis-solicitudes/', views.mis_solicitudes, name='mis_solicitudes'),

    # Medico
    path('medico/seleccion/', views.medico, name='medico'),
    path('medico/panel/', views.medico_dashboard, name='medico_panel'),
    path('medico/crear-cita/', views.crear_cita_medico, name='crear_cita_medico'),
    path('medico/consultas/', views.citas_recibidas_medico, name='citas_recibidas_medico'),
    path('medico/historial/', views.consulta_historial_medico, name='consulta_historial_medico'),

    # Odontologia
    path('odontologia/inicio/', views.odontologo, name='odontologo'),
    path('odontologia/citas/', views.citas_recibidas, name='citas_odonto'),
    path('odontologia/historial/', views.consulta_historial_odonto, name='historial_odonto'),

    # Acciones de Citas
    path('cita/atender/<int:cita_id>/', views.atender_cita, name='atender_cita'),
    path('cita/cancelar/<int:cita_id>/', views.cancelar_cita, name='cancelar_cita'),
    path('cita/refinar/<int:cita_id>/', views.refinar_cita, name='refinar_cita'),

    # Especialista
    path('especialista/inicio/', views.especialista, name='especialista'),
    path('especialista/citas/', views.citas_especialista, name='citas_especialista'),
    path('especialista/costos/', views.costos_especialista, name='costos_especialista'),
    path('especialista/nueva-cita/', views.nueva_cita_especialista, name='nueva_cita_especialista'),
    path('especialista/medicamentos/', views.medicamentos_especialista, name='medicamentos_especialista'),
    path('especialista/historial/', views.consulta_historial_especialista, name='consulta_historial_especialista'),

    # Laboratorista
    path('laboratorio/inicio/', views.laboratorista, name='laboratorio'),
    path('laboratorio/registro/', views.registrar_laboratorio, name='registrar_laboratorio'),
    path('laboratorio/pendientes/', views.solicitudes_pendientes_laboratorio, name='solicitudes_pendientes_laboratorio'),
    path('laboratorio/resultados/', views.resultados_laboratorio, name='resultados_laboratorio'),
    path('laboratorio/examenes/', views.catalogo_examenes, name='catalogo_examenes'),
    path('laboratorio/importar-examenes/', views.importar_catalogo_examenes, name='importar_catalogo_examenes'),

    # Administración
    path('administracion/inicio/', views.inicio_admin, name='inicio_admin'),
    path('administracion/menu/', views.menu_admin, name='menu_admin'),
    path('administracion/saldos/', views.saldos_admin, name='saldos_admin'),
    path('administracion/reporte/', views.reporte_admin, name='reporte_admin'),
    path('administracion/logs/', views.ver_logs, name='ver_logs'),
    path('administracion/ingresos/', views.ingresos_especialistas, name='ingresos_especialistas'),
    path('administracion/usuarios-pendientes/', views.usuarios_pendientes, name='usuarios_pendientes'),
    path('administracion/aprobar-usuario/<int:user_id>/', views.aprobar_usuario, name='aprobar_usuario'),

    # Póliza
    path('poliza/', views.poliza_inicio, name='poliza_inicio'),
    path('poliza/menu/', views.poliza_menu, name='poliza_menu'),
    path('poliza/crear/', views.poliza_crear, name='poliza_crear'),
    path('poliza/detalle/<int:poliza_id>/', views.poliza_detalle, name='poliza_detalle'),
    path('poliza/<int:poliza_id>/familiar/', views.poliza_registrar_familiar, name='poliza_registrar_familiar'),
    path('poliza/<int:poliza_id>/gasto/', views.poliza_registrar_gasto, name='poliza_registrar_gasto'),
    path('poliza/editar/<int:poliza_id>/', views.poliza_editar, name='poliza_editar'),
    path('poliza/planes/', views.plan_salud_lista, name='plan_salud_lista'),
    path('poliza/planes/editar/<int:plan_id>/', views.plan_salud_editar, name='plan_salud_editar'),
    path('poliza/planes/eliminar/<int:plan_id>/', views.plan_salud_eliminar, name='plan_salud_eliminar'),   

    # Selección de Roles
    path('home/', views.landing_page, name='home'),

    # Perfil de Usuario
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
    path('paciente/detalle/<int:paciente_id>/', views.detalle_paciente, name='detalle_paciente'),
    path('calendario/', views.calendario_citas, name='calendario_citas'),
    path('notificacion/marcar/<int:notif_id>/', views.marcar_notificacion, name='marcar_notificacion'),
    path('notificaciones/', views.mis_notificaciones, name='mis_notificaciones'),
    path('secretaria/solicitud/', views.crear_solicitud_view, name='crear_solicitud'),

    # 1 PANTALLA PARA PEDIR EL CORREO
    path('solicitud/correo/', auth_views.PasswordResetView.as_view(
        template_name='ipp1/contrasena/recuperar_password.html',
        subject_template_name='ipp1/contrasena/password_reset_subject.txt',
        html_email_template_name='ipp1/contrasena/password_reset_email.html',
    ), name='password_reset'),

    # 2 PANTALLA QUE AVISA QUE SE ENVIO EL CORREO
    path('solicitud/correo_enviado/', auth_views.PasswordResetDoneView.as_view(template_name='ipp1/contrasena/password_reset_done.html'), name='password_reset_done'),

    # 3 PANTALLA PARA RESTABLECER LA CONTRASEÑA
    path('solicitud/restablecer/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='ipp1/contrasena/password_reset_confirm.html'), name='password_reset_confirm'),

    # 4 PANTALLA QUE AVISA QUE SE RESTABLECIO LA CONTRASEÑA
    path('solicitud/restablecer_completo/', auth_views.PasswordResetCompleteView.as_view(template_name='ipp1/contrasena/password_reset_complete.html'), name='password_reset_complete'),

    # EXPORTAR DATOS (Solo Administración)
    path('exportar/pacientes/excel/', views.exportar_pacientes_excel, name='exportar_pacientes_excel'),
    path('exportar/pacientes/csv/', views.exportar_pacientes_csv, name='exportar_pacientes_csv'),
    path('exportar/reporte/excel/', views.exportar_reporte_excel, name='exportar_reporte_excel'),
    path('exportar/reporte/csv/', views.exportar_reporte_csv, name='exportar_reporte_csv'),

    # Importar desde Excel
    path('importar/pacientes/', views.importar_pacientes_excel, name='importar_pacientes_excel'),
    path('importar/gastos/', views.importar_gastos_excel, name='importar_gastos_excel'),
    path('importar/medicamentos/', views.importar_medicamentos_excel, name='importar_medicamentos_excel'),
    path('importar/nomina/poliza/<int:poliza_id>/', views.importar_nomina_poliza, name='importar_nomina_poliza'),

    # Facturación
    path('facturas/', views.facturas_lista, name='facturas_lista'),
    path('factura/<int:factura_id>/', views.factura_detalle, name='factura_detalle'),
    path('factura/generar/<int:cita_id>/', views.factura_generar, name='factura_generar'),

    # Historia Clínica
    path('historia-clinica/<int:paciente_id>/', views.historia_clinica_print, name='historia_clinica_print'),

    # Editar / Eliminar Paciente
    path('paciente/editar/<int:paciente_id>/', views.editar_paciente, name='editar_paciente'),
    path('paciente/eliminar/<int:paciente_id>/', views.desactivar_paciente, name='eliminar_paciente'),

    # Marcar Factura Pagada
    path('factura/pagar/<int:factura_id>/', views.marcar_factura_pagada, name='marcar_factura_pagada'),

    # Recibo de Factura
    path('factura/recibo/<int:factura_id>/', views.recibo_factura, name='recibo_factura'),

    # Reporte de Caja
    path('reporte/caja/', views.reporte_caja, name='reporte_caja'),

    # Recetas
    path('cita/<int:cita_id>/receta/', views.receta_crear, name='receta_crear'),
    path('receta/<int:receta_id>/print/', views.receta_print, name='receta_print'),

    # Vista compartida Secretaría-Póliza (estado de póliza del paciente)
    path('poliza/estado-paciente/<int:paciente_id>/', views.estado_poliza_paciente, name='estado_poliza_paciente'),

    # Gastos por paciente (Lic. Laudy)
    path('administracion/gastos-paciente/', views.gastos_por_paciente, name='gastos_por_paciente'),

    # Visualización cruzada Admin-Póliza
    path('administracion/resumen-afiliados/', views.resumen_afiliados, name='resumen_afiliados'),

    # Tasa de Cambio
    path('administracion/tasa-cambio/', views.tasa_cambio_lista, name='tasa_cambio_lista'),

    # Exportación múltiple de pacientes seleccionados
    path('exportar/pacientes/seleccionados/', views.exportar_pacientes_seleccionados, name='exportar_pacientes_seleccionados'),

    # Exportar gastos completos a Excel
    path('exportar/gastos/excel/', views.exportar_gastos_excel, name='exportar_gastos_excel'),

    #
    path('paciente/<int:paciente_id>/toggle/', views.toggle_paciente, name='toggle_paciente'),
]
