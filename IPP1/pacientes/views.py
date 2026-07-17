from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import Paciente, SolicitudSecretaria, SolicitudLaboratorio, PlanSalud, Poliza, GastoPaciente, Familiar, TarifaEspecialidad, Medicamento, Receta, Notificacion, LogActividad, Factura, PerfilUsuario
from .forms import PacienteForm, LoginForm, SolicitudSecretariaForm, SolicitudLaboratorioForm, ProcesarLaboratorioForm, TarifaEspecialidadForm, MedicamentoForm, RecetaForm, PlanSaludForm, PolizaForm, GastoPacienteForm, FamiliarForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils.timezone import now
import csv

# SOLICITUD DE CITA
@login_required
def crear_solicitud_view(request):
    if not (request.user.is_superuser or request.user.groups.filter(name='Secretaria').exists()):
        messages.error(request, "Acceso denegado.")
        return redirect('home')
    if request.method == 'POST':
        form = SolicitudSecretariaForm(request.POST)
        if form.is_valid():
            cita = form.save(commit=False)
            _vincular_poliza(cita)
            cita.save()
            form.save_m2m()
            if cita.especialista:
                _crear_notificacion(
                    cita.especialista,
                    f"Nueva cita asignada: {cita.paciente} el {cita.fecha_cita} a las {cita.hora_cita}",
                    reverse('calendario_citas')
                )
            _registrar_log(request, f'Creó solicitud de cita para {cita.paciente}', 'SolicitudSecretaria', cita.id)
            poliza = cita.poliza
            if poliza and poliza.plan and poliza.consultas_restantes() == 0:
                messages.warning(request, f'El paciente {cita.paciente} ha agotado las consultas de su póliza. Esta cita se registró como no cubierta.')
            else:
                messages.success(request, 'Solicitud de cita creada exitosamente.')
            return redirect('crear_solicitud')
    else:
        form = SolicitudSecretariaForm()

    ctx = {
        'form': form,
    }
    return render(request, 'ipp1/secretaria/crear_solicitud.html', ctx)

# LO DEL LOGIN
def login_view(request):
    """Vista para el inicio de sesión sin redirecciones ciegas en errores."""
    if request.user.is_authenticated:
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
        
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            usuario = form.cleaned_data.get('username')
            clave = form.cleaned_data.get('password')

            if not User.objects.filter(username=usuario).exists():
                messages.error(request, 'El nombre de usuario no existe. Por favor, regístrate.')
                return render(request, 'ipp1/compartidos/login.html', {'form': form})

            usuario_existente = User.objects.filter(username=usuario).first()
            if usuario_existente and not usuario_existente.is_active:
                return redirect('pendiente_aprobacion')

            usuario_obj = authenticate(request, username=usuario, password=clave)
            if usuario_obj is not None:
                login(request, usuario_obj)
                messages.error(request, 'No tienes permisos para acceder a esta seccion.')
                return redirect('home')
            else:
                messages.error(request, 'Contraseña incorrecta.')
                return render(request, 'ipp1/compartidos/login.html', {'form': form})
    else:
        form = LoginForm()

    return render(request, 'ipp1/compartidos/login.html', {'form': form})

@require_POST
def logout_view(request):
    """Cierra la sesión y redirige al login con un mensaje de éxito."""
    logout(request)
    messages.success(request, "Has cerrado sesión exitosamente. ¡Vuelve pronto!")
    return redirect('login')

# VISTA REGISTRO USUARIO/ROLES
ROLES_PERMITIDOS_REGISTRO = ['Secretaria', 'Medico', 'Odontologo', 'Laboratorio', 'Especialista']

def registro(request):
    """Vista para el registro de nuevos usuarios del sistema."""
    if request.method == 'POST':
        first_name = request.POST.get('name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password')
        rol_elegido = request.POST.get('rol', '').strip()

        if not username or not password:
            messages.error(request, 'El nombre de usuario y la contraseña son obligatorios.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya existe.')
        elif email and User.objects.filter(email=email).exists():
            messages.error(request, 'El correo electrónico ya está registrado.')
        else:
            try:
                validate_password(password)
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
                return render(request, 'ipp1/compartidos/registro.html', {'request': request})

            user = User.objects.create_user(
                username=username, email=email, password=password,
                first_name=first_name, last_name=last_name
            )
            user.is_active = False
            user.save()
            PerfilUsuario.objects.create(usuario=user, aprobado=False)
            
            if rol_elegido and rol_elegido in ROLES_PERMITIDOS_REGISTRO:
                grupo, created = Group.objects.get_or_create(name=rol_elegido)
                user.groups.add(grupo)
                messages.success(request, f'Usuario {username} registrado como {rol_elegido}.')
            else:
                messages.success(request, 'Usuario registrado con éxito.')
            _registrar_log(request, f'Registró usuario {username}', 'User', user.id)
            return redirect('login')
    
    return render(request, 'ipp1/compartidos/registro.html')

# APROBACION PENDIENTE
def pendiente_aprobacion(request):
    return render(request, 'ipp1/compartidos/pendiente_aprobacion.html')

@login_required
def usuarios_pendientes(request):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    pendientes = PerfilUsuario.objects.filter(aprobado=False).select_related('usuario', 'usuario__groups')
    return render(request, 'ipp1/admin/usuarios_pendientes.html', {'pendientes': pendientes})

@login_required
def aprobar_usuario(request, user_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    if request.method == 'POST':
        from django.utils import timezone
        perfil = get_object_or_404(PerfilUsuario, usuario_id=user_id)
        accion = request.POST.get('accion')
        if accion == 'aprobar':
            perfil.aprobado = True
            perfil.fecha_aprobacion = timezone.now()
            perfil.aprobado_por = request.user
            perfil.save()
            messages.success(request, f'Usuario {perfil.usuario.username} aprobado correctamente.')
        elif accion == 'rechazar':
            username = perfil.usuario.username
            perfil.usuario.delete()
            messages.success(request, f'Usuario {username} rechazado y eliminado.')
    return redirect('usuarios_pendientes')

# PERFIL DE USUARIO
@login_required
def perfil_usuario(request):
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()

        if request.POST.get('old_password'):
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, 'Perfil y contraseña actualizados correctamente.')
            else:
                messages.error(request, 'Corrige los errores de la contraseña.')
                return render(request, 'ipp1/compartidos/perfil.html', {'password_form': password_form})
        else:
            messages.success(request, 'Perfil actualizado correctamente.')

        return redirect('perfil_usuario')

    return render(request, 'ipp1/compartidos/perfil.html', {'password_form': password_form})

# VISTA SECRETARIA
@login_required
def secretaria(request):    
    if not (request.user.is_superuser or request.user.groups.filter(name='Secretaria').exists()):
        messages.error(request, "Acceso denegado: No tienes el rol de Secretaria.")
        return redirect('home')
    return render(request, 'ipp1/secretaria/inicio_secre.html')

# VISTA MEDICO
@login_required
def medico(request):
    """Selector de áreas dentro del Servicio Médico."""
    es_medico_real = request.user.groups.filter(name='Medico').exists()
    puede_acceder = (
        request.user.is_superuser
        or es_medico_real
        or request.user.groups.filter(name='Odontologo').exists()
        or request.user.groups.filter(name='Especialista').exists()
        or request.user.groups.filter(name='Laboratorio').exists()
    )
    if not puede_acceder:
        messages.warning(request, "No tienes permiso para acceder al Servicio Médico.")
        return redirect('home')
    context = {
        'titulo': 'Servicio Médico - Selección de Área',
        'es_medico_real': es_medico_real or request.user.is_superuser,
        'es_especialista': request.user.groups.filter(name='Especialista').exists() or request.user.is_superuser,
        'es_odontologo': request.user.groups.filter(name='Odontologo').exists() or request.user.is_superuser,
        'es_laboratorio': request.user.groups.filter(name='Laboratorio').exists() or request.user.is_superuser,
    }
    return render(request, 'ipp1/medico/seleccion_medico.html', context)

@login_required
def medico_dashboard(request):
    """Panel operativo de Medicina General."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Medico').exists()):
        messages.warning(request, "Acceso denegado.")
        return redirect('home')
    return render(request, 'ipp1/medico/inicio_medic.html')

@login_required
@require_POST
def atender_cita(request, cita_id):
    """Cambia el estado de la cita a 'Atendido' y registra el costo."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Medico').exists() or request.user.groups.filter(name='Odontologo').exists() or request.user.groups.filter(name='Especialista').exists()):
        messages.error(request, "No tienes permiso para atender citas.")
        return redirect('home')
    cita = get_object_or_404(SolicitudSecretaria, id=cita_id)
    if cita.especialista and cita.especialista != request.user and not request.user.is_superuser:
        messages.error(request, "Esta cita no te pertenece.")
        return redirect('home')
    cita.estado = 'Atendido'
    costo, m_medico, m_admin = cita.calcular_costo()
    cita.costo_consulta = costo
    cita.monto_medico = m_medico
    cita.monto_admin = m_admin
    cita.save()
    _registrar_log(request, f'Atendió cita de {cita.paciente}', 'SolicitudSecretaria', cita.id)
    tipo = 'cubierta por póliza' if cita.cubierto_por_poliza else 'particular'
    messages.success(request, f"Paciente {cita.paciente} atendido ({tipo}, ${costo:.2f}).")
    if request.user.groups.filter(name='Odontologo').exists():
        return redirect('citas_odonto')
    if request.user.groups.filter(name='Especialista').exists():
        return redirect('citas_especialista')
    return redirect('citas_recibidas_medico')

@login_required
@require_POST
def cancelar_cita(request, cita_id):
    """Cambia el estado de la cita a 'Cancelado'."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Medico').exists() or request.user.groups.filter(name='Odontologo').exists() or request.user.groups.filter(name='Especialista').exists()):
        messages.error(request, "No tienes permiso para cancelar citas.")
        return redirect('home')
    cita = get_object_or_404(SolicitudSecretaria, id=cita_id)
    if cita.especialista and cita.especialista != request.user and not request.user.is_superuser:
        messages.error(request, "Esta cita no te pertenece.")
        return redirect('home')
    cita.estado = 'Cancelado'
    cita.save()
    _registrar_log(request, f'Canceló cita de {cita.paciente}', 'SolicitudSecretaria', cita.id)
    messages.warning(request, f"Cita de {cita.paciente} cancelada.")
    if request.user.groups.filter(name='Odontologo').exists():
        return redirect('citas_odonto')
    if request.user.groups.filter(name='Especialista').exists():
        return redirect('citas_especialista')
    return redirect('citas_recibidas_medico')

@login_required
def citas_recibidas_medico(request):
    """Vista para ver las citas recibidas en Medicina General."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Medico').exists()):
        messages.warning(request, "Acceso denegado.")
        return redirect('home')
    
    citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(
        estado='En Espera',
        especialista__groups__name='Medico'
    ).order_by('fecha_cita', 'hora_cita')
    return render(request, 'ipp1/medico/citas_recibidas_medico.html', {'citas': citas})

@login_required
def consulta_historial_medico(request):
    """Vista para consultar el historial de pacientes en Medicina General."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Medico').exists()):
        messages.warning(request, "Acceso denegado.")
        return redirect('home')

    query = request.GET.get('q')
    base_qs = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(especialista__groups__name='Medico')
    if query:
        citas = base_qs.filter(
            Q(paciente__nombre__icontains=query) | 
            Q(paciente__apellido__icontains=query) | 
            Q(paciente__cedula__icontains=query)
        ).order_by('-fecha_cita', '-hora_cita')
    else:
        citas = base_qs.all().order_by('-fecha_cita', '-hora_cita')

    context = {
        'citas': citas,
        'navbar_brand': 'Sistema IPP - Servicio Médico',
        'title': 'Historial Médico',
        'page_heading': 'Historial Médico',
        'search_url_name': 'consulta_historial_medico',
        'back_url_name': 'medico_panel',
        'back_icon': 'bi-arrow-left',
        'back_text': 'Volver Atrás',
        'badge_class': 'bg-primary',
        'empty_message': 'No se encontraron registros médicos para mostrar.',
    }
    return render(request, 'ipp1/compartidos/historial_compartido.html', context)

# VISTA ODONTOLOGO
@login_required
def odontologo(request):
    """Vista principal para el área de Odontología."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Odontologo').exists()):
        messages.warning(request, "No tienes permiso para acceder a Odontología.")
        return redirect('home')
    return render(request, 'ipp1/odontologia/inicio_odonto.html')

@login_required
def citas_recibidas(request):
    """Vista para ver las citas recibidas en Odontología."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Odontologo').exists()):
        messages.warning(request, "No tienes permiso para acceder a esta área.")
        return redirect('home')
    
    citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(
        estado='En Espera',
        especialista__groups__name='Odontologo'
    ).order_by('fecha_cita', 'hora_cita')
    return render(request, 'ipp1/odontologia/citas_recibidas_odonto.html', {'citas': citas})

@login_required
def consulta_historial_odonto(request):
    """Vista para el historial odontológico."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Odontologo').exists()):
        messages.warning(request, "No tienes permiso para acceder a esta área.")
        return redirect('home')

    query = request.GET.get('q')
    base_qs = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(especialista__groups__name='Odontologo')
    if query:
        citas = base_qs.filter(
            Q(paciente__nombre__icontains=query) | 
            Q(paciente__apellido__icontains=query) | 
            Q(paciente__cedula__icontains=query)
        ).order_by('-fecha_cita', '-hora_cita')
    else:
        citas = base_qs.all().order_by('-fecha_cita', '-hora_cita')

    context = {
        'citas': citas,
        'navbar_brand': 'Sistema IPP - Odontología',
        'title': 'Historial de Odontología',
        'page_heading': 'Historial de Odontologia',
        'search_url_name': 'historial_odonto',
        'back_url_name': 'odontologo',
        'back_icon': 'bi-arrow-left',
        'back_text': 'Volver al Menú',
        'badge_class': 'bg-secondary',
        'empty_message': 'No se encontraron registros médicos para mostrar.',
    }
    return render(request, 'ipp1/compartidos/historial_compartido.html', context)

# VISITA ESPECIALISTA
@login_required
def especialista(request):
    """Vista principal para el Médico Especialista."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Especialista').exists()):
        messages.warning(request, "No tienes permiso para acceder a esta área.")
        return redirect('home')
    return render(request, 'ipp1/especialista/inicio_espec.html')

@login_required
def citas_especialista(request):
    """Lista de citas asignadas específicamente al especialista logueado."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Especialista').exists()):
        messages.warning(request, "Acceso denegado.")
        return redirect('home')
    
    # Filtramos citas asignadas a este usuario y que estén en espera
    citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(especialista=request.user, estado='En Espera').order_by('fecha_cita', 'hora_cita')
    return render(request, 'ipp1/especialista/citas_especialista.html', {'citas': citas})

@login_required
def costos_especialista(request):
    """Consulta y gestión de tarifas de especialidades."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Especialista').exists()):
        messages.warning(request, "Acceso denegado.")
        return redirect('home')

    tarifas = TarifaEspecialidad.objects.filter(activo=True).order_by('especialidad')

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear':
            form = TarifaEspecialidadForm(request.POST)
            if form.is_valid():
                t = form.save()
                _registrar_log(request, f'Creó tarifa {t.especialidad}', 'TarifaEspecialidad', t.id)
                messages.success(request, "Tarifa creada correctamente.")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        elif accion == 'editar':
            tarifa_id = request.POST.get('tarifa_id')
            tarifa = get_object_or_404(TarifaEspecialidad, id=tarifa_id)
            form = TarifaEspecialidadForm(request.POST, instance=tarifa)
            if form.is_valid():
                form.save()
                _registrar_log(request, f'Editó tarifa {tarifa.especialidad}', 'TarifaEspecialidad', tarifa.id)
                messages.success(request, "Tarifa actualizada.")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        elif accion == 'eliminar':
            tarifa_id = request.POST.get('tarifa_id')
            tarifa = get_object_or_404(TarifaEspecialidad, id=tarifa_id)
            tarifa.activo = False
            tarifa.save()
            _registrar_log(request, f'Desactivó tarifa {tarifa.especialidad}', 'TarifaEspecialidad', tarifa.id)
            messages.success(request, "Tarifa desactivada.")
        return redirect('costos_especialista')

    return render(request, 'ipp1/especialista/costos_especialista.html', {
        'tarifas': tarifas,
    })

@login_required
def nueva_cita_especialista(request):
    """Permite al especialista agendar una cita directamente."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Especialista').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    if request.method == 'POST':
        form = SolicitudSecretariaForm(request.POST)
        if form.is_valid():
            cita = form.save(commit=False)
            cita.especialista = request.user
            _vincular_poliza(cita)
            cita.save()
            form.save_m2m()
            poliza = cita.poliza
            if poliza and poliza.plan and poliza.consultas_restantes() == 0:
                messages.warning(request, f'El paciente {cita.paciente} ha agotado las consultas de su póliza. Se registró como no cubierta.')
            else:
                messages.success(request, 'Cita agendada correctamente.')
            return redirect('citas_especialista')
    else:
        form = SolicitudSecretariaForm(initial={'especialista': request.user})
    return render(request, 'ipp1/especialista/nueva_cita.html', {'form': form})

@login_required
def medicamentos_especialista(request):
    """Consulta y gestión de medicamentos/inventario."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Especialista').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    medicamentos = Medicamento.objects.filter(activo=True).order_by('nombre')

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear':
            form = MedicamentoForm(request.POST)
            if form.is_valid():
                m = form.save()
                _registrar_log(request, f'Registró medicamento {m.nombre}', 'Medicamento', m.id)
                messages.success(request, "Medicamento registrado.")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        elif accion == 'editar':
            med_id = request.POST.get('medicamento_id')
            med = get_object_or_404(Medicamento, id=med_id)
            form = MedicamentoForm(request.POST, instance=med)
            if form.is_valid():
                form.save()
                _registrar_log(request, f'Editó medicamento {med.nombre}', 'Medicamento', med.id)
                messages.success(request, "Medicamento actualizado.")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        elif accion == 'eliminar':
            med_id = request.POST.get('medicamento_id')
            med = get_object_or_404(Medicamento, id=med_id)
            med.activo = False
            med.save()
            _registrar_log(request, f'Desactivó medicamento {med.nombre}', 'Medicamento', med.id)
            messages.success(request, "Medicamento desactivado.")
        return redirect('medicamentos_especialista')

    return render(request, 'ipp1/especialista/medicamentos.html', {
        'medicamentos': medicamentos,
    })

# VISITA LABORATORISTA
@login_required
def laboratorista(request):
    """Panel principal para el área de Laboratorio."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Laboratorio').exists()):
        messages.warning(request, "No tienes permiso para acceder al área de Laboratorio.")
        return redirect('home')
    return render(request, 'ipp1/laboratorio/inicio_lab.html')

# VISTA REGISTRO DE LABORATORIO
@login_required
def registrar_laboratorio(request):
    """Permite registrar nuevas solicitudes de laboratorio."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Laboratorio').exists()):
        messages.error(request, "No tienes permiso para acceder a esta área.")
        return redirect('home')
    if request.method == 'POST':
        form = SolicitudLaboratorioForm(request.POST)
        if form.is_valid():
            lab = form.save()
            _registrar_log(request, f'Registró solicitud de laboratorio: {lab.prueba_laboratorio}', 'SolicitudLaboratorio', lab.id)
            messages.success(request, 'Solicitud de laboratorio registrada exitosamente.')
            return redirect('laboratorio')
        else:
            messages.error(request, 'Hubo un error al registrar la solicitud. Por favor, revise los datos.')
    else:
        form = SolicitudLaboratorioForm()

    ctx = {
        'form': form,
    }
    return render(request, 'ipp1/laboratorio/registro_lab.html', ctx)

@login_required
def solicitudes_pendientes_laboratorio(request):
    """Lista y procesamiento de solicitudes de laboratorio pendientes."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Laboratorio').exists()):
        messages.warning(request, "No tienes permiso para acceder a esta área.")
        return redirect('home')

    solicitudes = SolicitudLaboratorio.objects.filter(estado='Pendiente').order_by('-fecha_creacion')

    if request.method == 'POST':
        solicitud_id = request.POST.get('solicitud_id')
        solicitud = get_object_or_404(SolicitudLaboratorio, id=solicitud_id)
        form = ProcesarLaboratorioForm(request.POST, instance=solicitud)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.estado = 'Procesado'
            solicitud.fecha_procesamiento = now()
            solicitud.save()
            _registrar_log(request, f'Procesó examen de laboratorio: {solicitud.prueba_laboratorio}', 'SolicitudLaboratorio', solicitud.id)
            messages.success(request, f"Examen de {solicitud.paciente} procesado exitosamente.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    return render(request, 'ipp1/laboratorio/solicitudes_pendientes.html', {
        'solicitudes': solicitudes,
    })

# VISTAS DE ADMINISTRACIÓN
@login_required
def inicio_admin(request):
    """Panel inicial de administración."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, "No tienes permisos para acceder al área administrativa.")
        return redirect('home')
    return render(request, 'ipp1/administracion/inicio_admin.html')

@login_required
def menu_admin(request):
    """Menú detallado para asignar roles y especialidades."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    usuarios = User.objects.all().exclude(is_superuser=True) # Excluimos superusuarios para seguridad
    grupos = Group.objects.all()

    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        user_to_update = get_object_or_404(User, id=usuario_id)

        # Lógica para alternar estado de actividad (Activo/Inactivo)
        if 'toggle_status' in request.POST:
            user_to_update.is_active = not user_to_update.is_active
            user_to_update.save()
            estado = "activado" if user_to_update.is_active else "desactivado"
            _registrar_log(request, f'{estado.capitalize()} a {user_to_update.username}', 'User', user_to_update.id)
            messages.success(request, f"El acceso de '{user_to_update.username}' ha sido {estado}.")
            return redirect('menu_admin')

        # Lógica para asignar/quitar roles
        rol_nombre = request.POST.get('rol_nombre')
        
        if rol_nombre:
            # Agrega el rol sin eliminar los existentes
            grupo, _ = Group.objects.get_or_create(name=rol_nombre)
            user_to_update.groups.add(grupo)
            _registrar_log(request, f'Asignó rol {rol_nombre} a {user_to_update.username}', 'User', user_to_update.id)
            messages.success(request, f"Rol '{rol_nombre}' asignado a '{user_to_update.username}'.")
        else:
            # "-- Quitar Roles --" sí elimina todos
            user_to_update.groups.clear()
            _registrar_log(request, f'Quitó todos los roles de {user_to_update.username}', 'User', user_to_update.id)
            messages.success(request, f"Se han quitado todos los roles de '{user_to_update.username}'.")
        
        return redirect('menu_admin')

    return render(request, 'ipp1/administracion/menu_admin.html', {
        'usuarios': usuarios,
        'grupos': grupos
    })

@login_required
def saldos_admin(request):
    """Estatus y Saldos de Salud - lista de pacientes con saldo y afiliación."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    query = request.GET.get('q', '').strip()
    base = Paciente.objects.filter(activo=True)
    if query:
        base = base.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query) | Q(cedula__icontains=query) | Q(codigo_afiliado__icontains=query)
        )

    pacientes = base.order_by('apellido', 'nombre')
    total_afiliados = base.filter(status_afiliado='Afiliado').count()
    total_comunidad = base.filter(status_afiliado='Comunidad').count()

    return render(request, 'ipp1/administracion/saldos_admin.html', {
        'pacientes': pacientes,
        'total_afiliados': total_afiliados,
        'total_comunidad': total_comunidad,
        'query': query,
    })

@login_required
def reporte_admin(request):
    """Reporte de Consultas y Nómina - citas atendidas y cobros."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    citas_atendidas = SolicitudSecretaria.objects.filter(estado='Atendido').order_by('-fecha_cita', '-hora_cita')
    total_consultas = citas_atendidas.count()
    cobro_nomina_citas = citas_atendidas.filter(cobro_nomina=True).select_related('paciente', 'especialista')
    total_con_cobro = cobro_nomina_citas.count()
    monto_por_consulta = settings.MONTO_POR_CONSULTA
    total_nomina = total_con_cobro * monto_por_consulta

    total_ingresos = citas_atendidas.aggregate(total=Sum('costo_consulta'))['total'] or 0
    total_medico = citas_atendidas.aggregate(total=Sum('monto_medico'))['total'] or 0
    total_admin = citas_atendidas.aggregate(total=Sum('monto_admin'))['total'] or 0

    return render(request, 'ipp1/administracion/reporte_admin.html', {
        'citas_atendidas': citas_atendidas,
        'cobro_nomina_citas': cobro_nomina_citas,
        'cobro_nomina_count': total_con_cobro,
        'total_consultas': total_consultas,
        'total_con_cobro': total_con_cobro,
        'total_nomina': total_nomina,
        'monto_por_consulta': monto_por_consulta,
        'total_ingresos': total_ingresos,
        'total_medico': total_medico,
        'total_admin': total_admin,
    })

@login_required
def ver_logs(request):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    logs = LogActividad.objects.all().order_by('-fecha')[:500]
    return render(request, 'ipp1/administracion/logs.html', {'logs': logs})

@login_required
def ingresos_especialistas(request):
    """Reporte de ingresos generados por cada médico/especialista, agrupado por especialidad."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    ingresos = (SolicitudSecretaria.objects
                .filter(estado='Atendido', especialista__isnull=False)
                .values('especialista__username', 'especialista__first_name', 'especialista__last_name')
                .annotate(
                    total_cobrado=Sum('costo_consulta'),
                    total_medico=Sum('monto_medico'),
                    total_admin=Sum('monto_admin'),
                    total_citas=Count('id'),
                )
                .order_by('-total_cobrado'))
    for item in ingresos:
        item['total_cobrado'] = item['total_cobrado'] or 0
        item['total_medico'] = item['total_medico'] or 0
        item['total_admin'] = item['total_admin'] or 0

    # Determine specialty for each doctor
    especialidad_map = {}
    for item in ingresos:
        try:
            u = User.objects.get(username=item['especialista__username'])
            grupos = u.groups.values_list('name', flat=True)
            esp = grupos[0] if grupos else 'Especialista'
        except User.DoesNotExist:
            esp = 'Especialista'
        especialidad_map[item['especialista__username']] = esp
        item['especialidad'] = esp

    # Calculate per-specialty totals
    especialidad_totales = {}
    for item in ingresos:
        esp = item['especialidad']
        if esp not in especialidad_totales:
            especialidad_totales[esp] = {
                'total_cobrado': 0, 'total_medico': 0, 'total_admin': 0, 'total_citas': 0, 'doctores': 0,
            }
        especialidad_totales[esp]['total_cobrado'] += item['total_cobrado']
        especialidad_totales[esp]['total_medico'] += item['total_medico']
        especialidad_totales[esp]['total_admin'] += item['total_admin']
        especialidad_totales[esp]['total_citas'] += item['total_citas']
        especialidad_totales[esp]['doctores'] += 1

    gran_total = sum(item['total_cobrado'] for item in ingresos)
    return render(request, 'ipp1/administracion/ingresos_especialistas.html', {
        'ingresos': ingresos,
        'especialidad_totales': especialidad_totales,
        'gran_total': gran_total,
    })

# VISTAS DE PÓLIZA
@login_required
def poliza_inicio(request):
    """Panel principal del módulo Póliza."""
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administracion', 'Secretaria']).exists()):
        messages.error(request, "No tienes permisos para acceder a esta área.")
        return redirect('home')

    total_polizas = Poliza.objects.count()
    activas = Poliza.objects.filter(estado='Activo').count()
    inactivas = Poliza.objects.filter(estado='Inactivo').count()
    total_gastos = GastoPaciente.objects.aggregate(total=Sum('monto'))['total'] or 0
    planes = PlanSalud.objects.all()

    es_secretaria = request.user.groups.filter(name='Secretaria').exists()

    return render(request, 'ipp1/poliza/inicio_poliza.html', {
        'total_polizas': total_polizas,
        'activas': activas,
        'inactivas': inactivas,
        'total_gastos': total_gastos,
        'planes': planes,
        'es_secretaria': es_secretaria,
    })

@login_required
def poliza_menu(request):
    """Listado y gestión de pólizas."""
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administracion', 'Secretaria']).exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    query = request.GET.get('q', '').strip()
    polizas = Poliza.objects.select_related('paciente', 'plan').all().order_by('-fecha_creacion')
    if query:
        polizas = polizas.filter(
            Q(paciente__nombre__icontains=query)
            | Q(paciente__apellido__icontains=query)
            | Q(paciente__cedula__icontains=query)
        )

    if request.method == 'POST':
        accion = request.POST.get('accion')
        poliza_id = request.POST.get('poliza_id')
        poliza = get_object_or_404(Poliza, id=poliza_id)

        if accion == 'toggle_estado':
            poliza.estado = 'Inactivo' if poliza.estado == 'Activo' else 'Activo'
            poliza.save()
            messages.success(request, f"Póliza de {poliza.paciente} cambiada a '{poliza.estado}'.")
        elif accion == 'eliminar':
            poliza.delete()
            messages.success(request, "Póliza eliminada.")

        return redirect('poliza_menu')

    es_secretaria = request.user.groups.filter(name='Secretaria').exists()

    return render(request, 'ipp1/poliza/menu_poliza.html', {
        'polizas': polizas,
        'query': query,
        'es_secretaria': es_secretaria,
    })

@login_required
def poliza_crear(request):
    """Crear una nueva póliza para un paciente."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    if request.method == 'POST':
        form = PolizaForm(request.POST)
        if form.is_valid():
            poliza = form.save(commit=False)
            poliza.saldo_restante = poliza.plan.costo_mensual - form.cleaned_data['cuota_inicial']
            poliza.save()
            _registrar_log(request, f'Creó póliza para {poliza.paciente}', 'Poliza', poliza.id)
            messages.success(request, f"Póliza creada para {poliza.paciente.nombre} {poliza.paciente.apellido}.")
            return redirect('poliza_menu')
    else:
        form = PolizaForm()
    return render(request, 'ipp1/poliza/crear_poliza.html', {'form': form})

@login_required
def poliza_detalle(request, poliza_id):
    """Detalle de una póliza con gastos y familiares."""
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administracion', 'Secretaria']).exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    poliza = get_object_or_404(Poliza.objects.select_related('paciente', 'plan'), id=poliza_id)
    gastos = poliza.gastos.all().order_by('-fecha')
    familiares = poliza.familiares.all()
    citas = poliza.citas.select_related('especialista').order_by('-fecha_cita', '-hora_cita')
    total_gastado = gastos.aggregate(total=Sum('monto'))['total'] or 0

    es_secretaria = request.user.groups.filter(name='Secretaria').exists()

    return render(request, 'ipp1/poliza/detalle_poliza.html', {
        'poliza': poliza,
        'gastos': gastos,
        'familiares': familiares,
        'citas': citas,
        'total_gastado': total_gastado,
        'es_secretaria': es_secretaria,
    })

@login_required
def poliza_registrar_familiar(request, poliza_id):
    """Registrar un familiar en una póliza."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    poliza = get_object_or_404(Poliza, id=poliza_id)
    if poliza.familiares.count() >= 12:
        messages.error(request, "Esta póliza ya tiene el máximo de 12 familiares registrados.")
        return redirect('poliza_detalle', poliza_id=poliza.id)
    if request.method == 'POST':
        form = FamiliarForm(request.POST)
        if form.is_valid():
            familiar = form.save(commit=False)
            familiar.poliza = poliza
            familiar.save()
            messages.success(request, f"Familiar registrado en la póliza de {poliza.paciente}.")
            return redirect('poliza_detalle', poliza_id=poliza.id)
    else:
        form = FamiliarForm()
    return render(request, 'ipp1/poliza/registro_familiar_poliza.html', {'form': form, 'poliza': poliza})

@login_required
def poliza_registrar_gasto(request, poliza_id):
    """Registrar un gasto asociado a una póliza."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    poliza = get_object_or_404(Poliza, id=poliza_id)
    if request.method == 'POST':
        form = GastoPacienteForm(request.POST)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.poliza = poliza
            if gasto.monto > poliza.saldo_restante:
                messages.error(request, "El gasto supera el saldo restante de la póliza.")
                return redirect('poliza_registrar_gasto', poliza_id=poliza.id)
            gasto.save()
            poliza.saldo_restante -= gasto.monto
            poliza.save(update_fields=['saldo_restante'])
            _registrar_log(request, f'Registró gasto ${gasto.monto} en póliza de {poliza.paciente}', 'GastoPaciente', gasto.id)
            messages.success(request, f"Gasto registrado en la póliza de {poliza.paciente}.")
            return redirect('poliza_detalle', poliza_id=poliza.id)
    else:
        form = GastoPacienteForm()
    return render(request, 'ipp1/poliza/registrar_gasto.html', {'form': form, 'poliza': poliza})


@login_required
def poliza_editar(request, poliza_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    poliza = get_object_or_404(Poliza, id=poliza_id)
    if request.method == 'POST':
        form = PolizaForm(request.POST, instance=poliza)
        if form.is_valid():
            form.save()
            _registrar_log(request, f'Editó póliza de {poliza.paciente}', 'Poliza', poliza.id)
            messages.success(request, "Póliza actualizada exitosamente.")
            return redirect('poliza_detalle', poliza_id=poliza.id)
    else:
        form = PolizaForm(instance=poliza)
    return render(request, 'ipp1/poliza/editar_poliza.html', {'form': form, 'poliza': poliza})


@login_required
def plan_salud_lista(request):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    planes = PlanSalud.objects.all()
    if request.method == 'POST':
        form = PlanSaludForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan de salud creado.")
            return redirect('plan_salud_lista')
    else:
        form = PlanSaludForm()
    return render(request, 'ipp1/poliza/plan_salud_lista.html', {'planes': planes, 'form': form})


@login_required
def plan_salud_editar(request, plan_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    plan = get_object_or_404(PlanSalud, id=plan_id)
    if request.method == 'POST':
        form = PlanSaludForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan actualizado.")
            return redirect('plan_salud_lista')
    else:
        form = PlanSaludForm(instance=plan)
    return render(request, 'ipp1/poliza/plan_salud_form.html', {'form': form, 'plan': plan})


@login_required
def plan_salud_eliminar(request, plan_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    plan = get_object_or_404(PlanSalud, id=plan_id)
    plan.delete()
    messages.success(request, "Plan eliminado.")
    return redirect('plan_salud_lista')


# VISTA PACIENTES
@login_required
def registrar_paciente(request):
    """Vista para registrar nuevos pacientes."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Secretaria').exists()):
        messages.error(request, "Acceso denegado.")
        return redirect('home')
    q = request.GET.get('q', '').strip()
    pacientes_lista = Paciente.objects.filter(activo=True).order_by('-fecha_registro')
    if q:
        pacientes_lista = pacientes_lista.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(cedula__icontains=q) | Q(codigo_afiliado__icontains=q)
        )
    paginator = Paginator(pacientes_lista, 10)
    page_number = request.GET.get('page', 1)
    pacientes = paginator.get_page(page_number)

    if request.method == 'POST':
        form = PacienteForm(request.POST)
        if form.is_valid():
            p = form.save()
            _registrar_log(request, f'Registró paciente {p.nombre} {p.apellido}', 'Paciente', p.id)
            messages.success(request, 'Paciente registrado exitosamente.')
            return redirect('registrar_paciente')
    else:
        form = PacienteForm()

    ctx = {'form': form, 'pacientes': pacientes, 'q': q}
    return render(request, 'ipp1/secretaria/regis_pacient.html', ctx)

# CALENDARIO DE CITAS
@login_required
def calendario_citas(request):
    user = request.user
    if not (user.is_superuser or user.groups.filter(name__in=['Administracion', 'Secretaria', 'Medico', 'Odontologo', 'Especialista', 'Laboratorio']).exists()):
        messages.error(request, 'No tienes permisos para acceder al calendario.')
        return redirect('home')
    if user.is_superuser or user.groups.filter(name='Administracion').exists():
        citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').all()
    elif user.groups.filter(name='Medico').exists():
        citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(especialista__groups__name='Medico')
    elif user.groups.filter(name='Odontologo').exists():
        citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(especialista__groups__name='Odontologo')
    elif user.groups.filter(name='Especialista').exists():
        citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').filter(especialista=user)
    elif user.groups.filter(name='Secretaria').exists():
        citas = SolicitudSecretaria.objects.select_related('paciente', 'especialista').all()
    else:
        citas = SolicitudSecretaria.objects.none()

    citas = citas.order_by('-fecha_cita', '-hora_cita')

    citas_por_fecha = []
    fecha_actual = None
    grupo = None
    for c in citas:
        if c.fecha_cita != fecha_actual:
            grupo = {'fecha': c.fecha_cita, 'citas': []}
            citas_por_fecha.append(grupo)
            fecha_actual = c.fecha_cita
        grupo['citas'].append(c)

    return render(request, 'ipp1/compartidos/calendario_citas.html', {'citas_por_fecha': citas_por_fecha})

# DETALLE DE PACIENTE
@login_required
def detalle_paciente(request, paciente_id):
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administracion', 'Secretaria', 'Medico', 'Odontologo', 'Especialista', 'Laboratorio']).exists()):
        messages.error(request, 'No tienes permisos para ver este paciente.')
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    citas = SolicitudSecretaria.objects.filter(paciente=paciente).order_by('-fecha_cita', '-hora_cita')
    laboratorios = SolicitudLaboratorio.objects.filter(paciente=paciente).order_by('-fecha_solicitud')
    poliza_activa = Poliza.objects.filter(paciente=paciente, estado='Activo').select_related('plan').first()
    recetas = Receta.objects.filter(cita__paciente=paciente).select_related('medicamento', 'cita__especialista').order_by('-fecha_prescrita')
    return render(request, 'ipp1/compartidos/detalle_paciente.html', {
        'paciente': paciente,
        'citas': citas,
        'laboratorios': laboratorios,
        'poliza_activa': poliza_activa,
        'recetas': recetas,
    })

@login_required
def landing_page(request):
    """Página de inicio del sistema con selección de roles filtrados."""
    is_admin = request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()
    es_medico_real = request.user.groups.filter(name='Medico').exists() or is_admin
    puede_entrar_servicio_medico = (
        es_medico_real
        or request.user.groups.filter(name='Odontologo').exists()
        or request.user.groups.filter(name='Especialista').exists()
        or request.user.groups.filter(name='Laboratorio').exists()
    )

    context = {
        'titulo': 'Sistema IPP - Inicio',
        'es_admin': is_admin,
        'es_secretaria': request.user.groups.filter(name='Secretaria').exists() or is_admin,
        'puede_entrar_servicio_medico': puede_entrar_servicio_medico,
    }
    return render(request, 'ipp1/compartidos/selec_roles.html', context)


#  EXPORTACIÓN DE DATOS (Solo Administración)

def _es_admin(user):
    return user.is_superuser or user.groups.filter(name='Administracion').exists()


def _crear_notificacion(usuario, mensaje, url=None):
    Notificacion.objects.create(usuario=usuario, mensaje=mensaje, url=url)


def _registrar_log(request, accion, modelo=None, objeto_id=None, detalle=None):
    LogActividad.objects.create(
        usuario=request.user if request.user.is_authenticated else None,
        accion=accion,
        modelo=modelo,
        objeto_id=objeto_id,
        detalle=detalle,
    )


def _vincular_poliza(cita):
    from .models import Poliza
    if cita.poliza_id:
        return
    if cita.paciente.status_afiliado == 'Particular':
        cita.cubierto_por_poliza = False
        return
    if cita.especialista and cita.especialista.groups.filter(name='Medico').exists():
        cita.cubierto_por_poliza = False
        return
    poliza_activa = Poliza.objects.filter(
        paciente=cita.paciente,
        estado='Activo'
    ).first()
    if poliza_activa and poliza_activa.plan:
        cita.cubierto_por_poliza = True
        cita.poliza = poliza_activa
        restantes = poliza_activa.consultas_restantes()
        if restantes is None or restantes > 0:
            cita.cubierto_por_poliza = True
        else:
            cita.cubierto_por_poliza = False


@require_POST
@login_required
def marcar_notificacion(request, notif_id):
    notif = get_object_or_404(Notificacion, id=notif_id, usuario=request.user)
    notif.leida = True
    notif.save()
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
def exportar_pacientes_excel(request):
    if not _es_admin(request.user):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    import openpyxl
    query = request.GET.get('q', '').strip()
    pacientes = Paciente.objects.filter(activo=True)
    if query:
        pacientes = pacientes.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query) | Q(cedula__icontains=query)
        )
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pacientes"
    ws.append(["Nombre", "Apellido", "Cédula", "Teléfono", "Status", "Saldo"])
    for p in pacientes:
        ws.append([p.nombre, p.apellido, p.cedula, p.telefono, p.status_afiliado, float(p.saldo_plan_salud)])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="pacientes.xlsx"'
    wb.save(response)
    return response


@login_required
def exportar_pacientes_csv(request):
    if not _es_admin(request.user):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    query = request.GET.get('q', '').strip()
    pacientes = Paciente.objects.filter(activo=True)
    if query:
        pacientes = pacientes.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query) | Q(cedula__icontains=query)
        )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pacientes.csv"'
    writer = csv.writer(response)
    writer.writerow(["Nombre", "Apellido", "Cédula", "Teléfono", "Status", "Saldo"])
    for p in pacientes:
        writer.writerow([p.nombre, p.apellido, p.cedula, p.telefono, p.status_afiliado, float(p.saldo_plan_salud)])
    return response


@login_required
def exportar_reporte_excel(request):
    if not _es_admin(request.user):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    import openpyxl
    citas = SolicitudSecretaria.objects.filter(estado='Atendido').select_related('paciente', 'especialista').order_by('-fecha_cita')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte"
    ws.append(["#", "Paciente", "Cédula", "Especialista", "Fecha", "Hora", "Cobro Nómina"])
    for i, c in enumerate(citas, 1):
        ws.append([
            i,
            f"{c.paciente.nombre} {c.paciente.apellido}",
            c.paciente.cedula,
            c.especialista.get_full_name() or c.especialista.username if c.especialista else "-",
            c.fecha_cita.strftime("%d/%m/%Y"),
            c.hora_cita.strftime("%H:%M"),
            "Sí" if c.cobro_nomina else "No"
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="reporte_consultas.xlsx"'
    wb.save(response)
    return response


@login_required
def exportar_reporte_csv(request):
    if not _es_admin(request.user):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    citas = SolicitudSecretaria.objects.filter(estado='Atendido').select_related('paciente', 'especialista').order_by('-fecha_cita')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reporte_consultas.csv"'
    writer = csv.writer(response)
    writer.writerow(["#", "Paciente", "Cédula", "Especialista", "Fecha", "Hora", "Cobro Nómina"])
    for i, c in enumerate(citas, 1):
        writer.writerow([
            i,
            f"{c.paciente.nombre} {c.paciente.apellido}",
            c.paciente.cedula,
            c.especialista.get_full_name() or c.especialista.username if c.especialista else "-",
            c.fecha_cita.strftime("%d/%m/%Y"),
            c.hora_cita.strftime("%H:%M"),
            "Sí" if c.cobro_nomina else "No"
        ])
    return response


@login_required
def importar_pacientes_excel(request):
    """Importa pacientes desde un archivo Excel."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    if request.method == 'POST' and request.FILES.get('archivo'):
        import openpyxl
        archivo = request.FILES['archivo']
        try:
            wb = openpyxl.load_workbook(archivo, read_only=True)
            ws = wb.active
            creados = 0
            errores = []
            for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    nombre, apellido, cedula, telefono, direccion, fecha_nac, status = (row + (None,)*7)[:7]
                    if not all([nombre, apellido, cedula, fecha_nac]):
                        errores.append(f"Fila {i}: faltan datos obligatorios")
                        continue
                    if isinstance(fecha_nac, str):
                        from datetime import datetime
                        fecha_nac = datetime.strptime(fecha_nac, '%d/%m/%Y').date()
                    if Paciente.objects.filter(cedula=cedula).exists():
                        errores.append(f"Fila {i}: cédula {cedula} ya existe")
                        continue
                    Paciente.objects.create(
                        nombre=str(nombre).strip(),
                        apellido=str(apellido).strip(),
                        cedula=str(cedula).strip(),
                        telefono=str(telefono).strip() if telefono else None,
                        direccion=str(direccion).strip() if direccion else None,
                        fecha_nacimiento=fecha_nac,
                        status_afiliado=str(status).strip() if status else 'Comunidad',
                    )
                    creados += 1
                except Exception as e:
                    errores.append(f"Fila {i}: {e}")
            if creados:
                messages.success(request, f"{creados} paciente(s) importado(s) correctamente.")
            if errores:
                for err in errores[:5]:
                    messages.warning(request, err)
                if len(errores) > 5:
                    messages.warning(request, f"...y {len(errores)-5} error(es) más.")
            _registrar_log(request, f'Importó {creados} pacientes desde Excel', 'Paciente')
        except Exception as e:
            messages.error(request, f"Error al leer el archivo: {e}")
        return redirect('saldos_admin')
    return render(request, 'ipp1/administracion/importar_pacientes.html')


@login_required
def facturas_lista(request):
    """Listado de facturas generadas."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists() or request.user.groups.filter(name='Secretaria').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    facturas = Factura.objects.all().order_by('-fecha_emision')
    return render(request, 'ipp1/facturacion/facturas_lista.html', {'facturas': facturas})


@login_required
def factura_detalle(request, factura_id):
    """Detalle de una factura."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists() or request.user.groups.filter(name='Secretaria').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    factura = get_object_or_404(Factura, id=factura_id)
    return render(request, 'ipp1/facturacion/factura_detalle.html', {'factura': factura})


@login_required
def factura_generar(request, cita_id):
    """Genera una factura opcional para una cita atendida."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    cita = get_object_or_404(SolicitudSecretaria, id=cita_id, estado='Atendido')
    if hasattr(cita, 'factura'):
        messages.info(request, "Esta cita ya tiene una factura.")
        return redirect('factura_detalle', factura_id=cita.factura.id)
    if request.method == 'POST':
        iva = Decimal(request.POST.get('iva', '0'))
        descripcion = request.POST.get('descripcion', '')
        subtotal = cita.costo_consulta or Decimal('0.00')
        total = subtotal + (subtotal * iva / Decimal('100'))
        factura = Factura.objects.create(
            cita=cita,
            paciente_nombre=f"{cita.paciente.nombre} {cita.paciente.apellido}",
            paciente_cedula=cita.paciente.cedula,
            especialista_nombre=cita.especialista.get_full_name() or cita.especialista.username if cita.especialista else '',
            descripcion=descripcion,
            subtotal=subtotal,
            iva=subtotal * iva / Decimal('100'),
            total=total,
        )
        _registrar_log(request, f'Generó factura {factura.numero_factura} para cita {cita.id}', 'Factura', factura.id)
        messages.success(request, f"Factura {factura.numero_factura} generada.")
        return redirect('factura_detalle', factura_id=factura.id)
    return render(request, 'ipp1/facturacion/factura_generar.html', {'cita': cita})


@login_required
def historia_clinica_print(request, paciente_id):
    """Vista imprimible de la historia clínica del paciente."""
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administracion', 'Secretaria', 'Medico', 'Odontologo', 'Especialista', 'Laboratorio']).exists()):
        messages.error(request, 'No tienes permisos para ver la historia clínica.')
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    citas = SolicitudSecretaria.objects.filter(paciente=paciente).select_related('especialista').order_by('-fecha_cita', '-hora_cita')
    laboratorios = SolicitudLaboratorio.objects.filter(paciente=paciente).order_by('-fecha_solicitud')
    recetas = Receta.objects.filter(cita__paciente=paciente).select_related('medicamento', 'cita__especialista').order_by('-fecha_prescrita')
    return render(request, 'ipp1/compartidos/historia_clinica_print.html', {
        'paciente': paciente,
        'citas': citas,
        'laboratorios': laboratorios,
        'recetas': recetas,
    })


#  EDITAR / ELIMINAR PACIENTE 
@login_required
def editar_paciente(request, paciente_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Secretaria').exists() or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, "Acceso denegado.")
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    if request.method == 'POST':
        form = PacienteForm(request.POST, instance=paciente)
        if form.is_valid():
            form.save()
            _registrar_log(request, f'Editó paciente {paciente.nombre} {paciente.apellido}', 'Paciente', paciente.id)
            messages.success(request, 'Paciente actualizado exitosamente.')
            if request.user.groups.filter(name='Secretaria').exists():
                return redirect('registrar_paciente')
            return redirect('detalle_paciente', paciente_id=paciente.id)
    else:
        form = PacienteForm(instance=paciente)
    return render(request, 'ipp1/compartidos/editar_paciente.html', {'form': form, 'paciente': paciente})


@login_required
@require_POST
def eliminar_paciente(request, paciente_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Secretaria').exists() or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, "Acceso denegado.")
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    _registrar_log(request, f'Eliminó paciente {paciente.nombre} {paciente.apellido} ({paciente.cedula})', 'Paciente', paciente.id)
    paciente.delete()
    messages.success(request, f"Paciente {paciente.nombre} {paciente.apellido} eliminado.")
    if request.user.groups.filter(name='Administracion').exists() and not request.user.groups.filter(name='Secretaria').exists():
        return redirect('saldos_admin')
    return redirect('registrar_paciente')


#  PAGOS / FACTURACIÓN 
@login_required
def marcar_factura_pagada(request, factura_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists() or request.user.groups.filter(name='Secretaria').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    factura = get_object_or_404(Factura, id=factura_id)
    if request.method == 'POST':
        metodo = request.POST.get('metodo_pago')
        if not metodo:
            messages.error(request, "Seleccione un método de pago.")
            return redirect('marcar_factura_pagada', factura_id=factura.id)
        factura.pagada = True
        factura.metodo_pago = metodo
        factura.fecha_pago = now()
        factura.save()
        _registrar_log(request, f'Registró pago de {factura.numero_factura} ({metodo})', 'Factura', factura.id)
        messages.success(request, f"Pago registrado para {factura.numero_factura}.")
        return redirect('factura_detalle', factura_id=factura.id)
    return render(request, 'ipp1/facturacion/marcar_pagada.html', {'factura': factura})


@login_required
def recibo_factura(request, factura_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists() or request.user.groups.filter(name='Secretaria').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    factura = get_object_or_404(Factura, id=factura_id)
    return render(request, 'ipp1/facturacion/recibo_factura.html', {'factura': factura})


@login_required
def reporte_caja(request):
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    from django.utils.timezone import localdate
    hoy = localdate()
    fecha_str = request.GET.get('fecha', '')
    if fecha_str:
        from datetime import datetime
        try:
            fecha_filtro = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_filtro = hoy
    else:
        fecha_filtro = hoy
    facturas = Factura.objects.filter(pagada=True, fecha_pago__date=fecha_filtro).order_by('fecha_pago')
    total_efectivo = facturas.filter(metodo_pago='Efectivo').aggregate(t=Sum('total'))['t'] or 0
    total_debito = facturas.filter(metodo_pago='Tarjeta Débito').aggregate(t=Sum('total'))['t'] or 0
    total_credito = facturas.filter(metodo_pago='Tarjeta Crédito').aggregate(t=Sum('total'))['t'] or 0
    total_transferencia = facturas.filter(metodo_pago='Transferencia').aggregate(t=Sum('total'))['t'] or 0
    total_otro = facturas.filter(metodo_pago='Otro').aggregate(t=Sum('total'))['t'] or 0
    total_dia = facturas.aggregate(t=Sum('total'))['t'] or 0
    return render(request, 'ipp1/administracion/reporte_caja.html', {
        'facturas': facturas,
        'fecha': fecha_filtro,
        'total_efectivo': total_efectivo,
        'total_debito': total_debito,
        'total_credito': total_credito,
        'total_transferencia': total_transferencia,
        'total_otro': total_otro,
        'total_dia': total_dia,
    })


# RECETAS
@login_required
def receta_crear(request, cita_id):
    if not (request.user.is_superuser or request.user.groups.filter(name='Medico').exists() or request.user.groups.filter(name='Odontologo').exists() or request.user.groups.filter(name='Especialista').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    cita = get_object_or_404(SolicitudSecretaria, id=cita_id, estado='Atendido')
    if cita.especialista and cita.especialista != request.user and not request.user.is_superuser:
        messages.error(request, "Esta cita no te pertenece.")
        return redirect('home')
    if request.method == 'POST':
        form = RecetaForm(request.POST)
        if form.is_valid():
            receta = form.save(commit=False)
            receta.cita = cita
            receta.save()
            if receta.medicamento and receta.medicamento.cantidad_stock:
                med = receta.medicamento
                med.cantidad_stock -= receta.cantidad
                if med.cantidad_stock < 0:
                    med.cantidad_stock = 0
                med.save(update_fields=['cantidad_stock'])
            _registrar_log(request, f'Creó receta para {cita.paciente}', 'Receta', receta.id)
            messages.success(request, "Receta registrada exitosamente.")
            if request.user.groups.filter(name='Medico').exists():
                return redirect('citas_recibidas_medico')
            if request.user.groups.filter(name='Odontologo').exists():
                return redirect('citas_odonto')
            if request.user.groups.filter(name='Especialista').exists():
                return redirect('citas_especialista')
            return redirect('reporte_admin')
    else:
        form = RecetaForm()
    return render(request, 'ipp1/especialista/receta_crear.html', {'form': form, 'cita': cita})

# VISTAS COMPARTIDAS
@login_required
def estado_poliza_paciente(request, paciente_id):
    """Vista compartida Secretaría/Póliza: estado de póliza del paciente."""
    if not (request.user.is_superuser
            or request.user.groups.filter(name__in=['Administracion', 'Secretaria']).exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    poliza = Poliza.objects.filter(paciente=paciente).select_related('plan').first()
    total_gastado = 0
    gastos_recientes = []
    if poliza:
        gastos_recientes = poliza.gastos.all().order_by('-fecha')[:10]
        total_gastado = poliza.gastos.aggregate(total=Sum('monto'))['total'] or 0
    return render(request, 'ipp1/compartidos/estado_poliza_paciente.html', {
        'paciente': paciente,
        'poliza': poliza,
        'total_gastado': total_gastado,
        'gastos_recientes': gastos_recientes,
    })



# VISTA GASTOS POR PACIENTE (ADMIN)
@login_required
def gastos_por_paciente(request):
    """Gastos detallados por paciente accesible desde Admin y Póliza."""
    if not (request.user.is_superuser
            or request.user.groups.filter(name__in=['Administracion', 'Secretaria']).exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    q = request.GET.get('q', '').strip()
    pacientes = Paciente.objects.filter(activo=True).order_by('apellido')
    if q:
        pacientes = pacientes.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(cedula__icontains=q)
        )

    gastos_por_paciente = GastoPaciente.objects.filter(
        poliza__paciente__activo=True
    ).values('poliza__paciente__id').annotate(total=Sum('monto'))

    citas_por_paciente = SolicitudSecretaria.objects.filter(
        paciente__activo=True, estado='Atendido', costo_consulta__gt=0
    ).values('paciente__id').annotate(
        total_costo=Sum('costo_consulta'),
        total_medico=Sum('monto_medico'),
        total_admin=Sum('monto_admin'),
    )

    polizas_activas = {
        p.paciente_id: p
        for p in Poliza.objects.filter(paciente__activo=True, estado='Activo')
    }

    gastos_map = {g['poliza__paciente__id']: g['total'] or 0 for g in gastos_por_paciente}
    citas_map = {c['paciente__id']: c for c in citas_por_paciente}

    data = []
    for p in pacientes:
        gastos_poliza = gastos_map.get(p.id, 0)
        cita = citas_map.get(p.id, {})
        citas_pagadas = cita.get('total_costo', 0) or 0
        total_medico = cita.get('total_medico', 0) or 0
        total_admin = cita.get('total_admin', 0) or 0
        total_gastado = gastos_poliza + citas_pagadas
        poliza_activa = polizas_activas.get(p.id)
        saldo = poliza_activa.saldo_restante if poliza_activa else 0

        if total_gastado > 0 or poliza_activa:
            data.append({
                'paciente': p,
                'total_gastado': total_gastado,
                'total_medico': total_medico,
                'total_admin': total_admin,
                'gastos_poliza': gastos_poliza,
                'citas_pagadas': citas_pagadas,
                'poliza_activa': poliza_activa,
                'saldo': saldo,
            })

    total_global = sum(d['total_gastado'] for d in data)
    return render(request, 'ipp1/administracion/gastos_por_paciente.html', {
        'data': data,
        'q': q,
        'total_global': total_global,
    })

# VISUALIZACIÓN CRUZADA: GASTOS POR AFILIADO
@login_required
def resumen_afiliados(request):
    """Cross-module spending visualization — Admin and Póliza."""
    if not (request.user.is_superuser
            or request.user.groups.filter(name__in=['Administracion', 'Secretaria']).exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    afiliados = Paciente.objects.filter(status_afiliado='Afiliado', activo=True).order_by('apellido')

    gastos_por_paciente = GastoPaciente.objects.filter(
        poliza__paciente__status_afiliado='Afiliado', poliza__paciente__activo=True
    ).values('poliza__paciente__id').annotate(total=Sum('monto'))

    citas_por_paciente = SolicitudSecretaria.objects.filter(
        paciente__status_afiliado='Afiliado', paciente__activo=True, estado='Atendido'
    ).values('paciente__id').annotate(
        total_costo=Sum('costo_consulta'),
    )

    citas_cubiertas = SolicitudSecretaria.objects.filter(
        paciente__status_afiliado='Afiliado', paciente__activo=True,
        estado='Atendido', cubierto_por_poliza=True
    ).values('paciente__id').annotate(count=Count('id'))

    polizas_map = {}
    for pol in Poliza.objects.filter(paciente__status_afiliado='Afiliado', paciente__activo=True):
        polizas_map[pol.paciente_id] = pol

    gastos_map = {g['poliza__paciente__id']: g['total'] or 0 for g in gastos_por_paciente}
    citas_map = {c['paciente__id']: c['total_costo'] or 0 for c in citas_por_paciente}
    cubiertas_map = {c['paciente__id']: c['count'] for c in citas_cubiertas}

    data = []
    for p in afiliados:
        poliza = polizas_map.get(p.id)
        gastos_poliza = gastos_map.get(p.id, 0)
        citas_totales = citas_map.get(p.id, 0)
        citas_usadas = cubiertas_map.get(p.id, 0)
        data.append({
            'paciente': p,
            'poliza': poliza,
            'gastos_poliza': gastos_poliza,
            'citas_totales': citas_totales,
            'citas_usadas': citas_usadas,
            'saldo_poliza': poliza.saldo_restante if poliza else 0,
        })

    return render(request, 'ipp1/administracion/resumen_afiliados.html', {
        'data': data,
        'total_afiliados': afiliados.count(),
    })

# EXPORTAR GASTOS A EXCEL
@login_required
def exportar_gastos_excel(request):
    """Export a comprehensive Excel with spending by patient/consultation/doctor."""
    if not (request.user.is_superuser
            or request.user.groups.filter(name__in=['Administracion', 'Secretaria']).exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()

    # Hoja 1: Gastos por Paciente
    ws1 = wb.active
    ws1.title = "Gastos por Paciente"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2C6E9C", end_color="2C6E9C", fill_type="solid")
    headers = ['Paciente', 'Cédula', 'Status', 'Gastos Póliza', 'Citas Pagadas', 'Total Gastado', 'Saldo Póliza']
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    gastos_data = GastoPaciente.objects.filter(
        poliza__paciente__activo=True
    ).values('poliza__paciente__id').annotate(total=Sum('monto'))
    gastos_map = {g['poliza__paciente__id']: g['total'] or 0 for g in gastos_data}

    citas_data = SolicitudSecretaria.objects.filter(
        paciente__activo=True, estado='Atendido', costo_consulta__gt=0
    ).values('paciente__id').annotate(total=Sum('costo_consulta'))
    citas_map = {c['paciente__id']: c['total'] or 0 for c in citas_data}

    polizas_map = {
        p.paciente_id: p
        for p in Poliza.objects.filter(paciente__activo=True)
    }

    row = 2
    for p in Paciente.objects.filter(activo=True).order_by('apellido'):
        gp = gastos_map.get(p.id, 0)
        cp = citas_map.get(p.id, 0)
        poliza = polizas_map.get(p.id)
        saldo = poliza.saldo_restante if poliza else 0
        ws1.cell(row=row, column=1, value=f"{p.nombre} {p.apellido}")
        ws1.cell(row=row, column=2, value=p.cedula)
        ws1.cell(row=row, column=3, value=p.status_afiliado)
        ws1.cell(row=row, column=4, value=float(gp))
        ws1.cell(row=row, column=5, value=float(cp))
        ws1.cell(row=row, column=6, value=float(gp + cp))
        ws1.cell(row=row, column=7, value=float(saldo))
        row += 1

    # Hoja 2: Consultas con cobro nómina
    ws2 = wb.create_sheet("Cobro Nómina")
    headers2 = ['Paciente', 'Especialista', 'Fecha', 'Costo', 'Médico', 'Admin', 'Cobro Nómina']
    for col, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    row = 2
    for c in SolicitudSecretaria.objects.filter(estado='Atendido').select_related('paciente', 'especialista').order_by('-fecha_cita'):
        ws2.cell(row=row, column=1, value=f"{c.paciente.nombre} {c.paciente.apellido}")
        ws2.cell(row=row, column=2, value=c.especialista.get_full_name() or c.especialista.username if c.especialista else '-')
        ws2.cell(row=row, column=3, value=c.fecha_cita.strftime('%d/%m/%Y'))
        ws2.cell(row=row, column=4, value=float(c.costo_consulta))
        ws2.cell(row=row, column=5, value=float(c.monto_medico))
        ws2.cell(row=row, column=6, value=float(c.monto_admin))
        ws2.cell(row=row, column=7, value='Sí' if c.cobro_nomina else 'No')
        row += 1

    ws2.column_dimensions['A'].width = 30
    ws2.column_dimensions['B'].width = 30
    ws2.column_dimensions['C'].width = 15

    for ws in [ws1]:
        ws.column_dimensions['A'].width = 35
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 14
        ws.column_dimensions['D'].width = 16
        ws.column_dimensions['E'].width = 16
        ws.column_dimensions['F'].width = 16
        ws.column_dimensions['G'].width = 14

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=gastos_completos.xlsx'
    wb.save(response)
    return response


@login_required
def exportar_pacientes_seleccionados(request):
    """Exporta pacientes seleccionados a Excel."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta seccion.')
        return redirect('home')
    import openpyxl
    ids = request.GET.get('ids', '')
    if not ids:
        messages.warning(request, "No seleccionaste pacientes.")
        return redirect('saldos_admin')
    id_list = [int(x) for x in ids.split(',') if x.isdigit()]
    pacientes = Paciente.objects.filter(id__in=id_list).order_by('apellido')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pacientes Seleccionados"
    ws.append(['Código', 'Nombre', 'Cédula', 'Teléfono', 'Status', 'Categoría', 'Saldo'])
    for p in pacientes:
        ws.append([
            p.codigo_afiliado or '',
            f"{p.nombre} {p.apellido}",
            p.cedula,
            p.telefono or '',
            p.status_afiliado,
            p.categoria_afiliado,
            float(p.saldo_plan_salud),
        ])
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 35
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 14
    ws.column_dimensions['E'].width = 14
    ws.column_dimensions['F'].width = 14
    ws.column_dimensions['G'].width = 12
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=pacientes_seleccionados.xlsx'
    wb.save(response)
    return response

# ACTIVAR DESACTIVAR
@login_required
def toggle_paciente(request, paciente_id):
    """Activa o desactiva un paciente."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Administracion').exists()):
        messages.error(request, 'No tienes permisos.')
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    paciente.activo = not paciente.activo
    paciente.save()
    
    estado = "activado" if paciente.activo else "desactivado"
    _registrar_log(request, f'{"Activó" if paciente.activo else "Desactivó"} paciente {paciente.nombre} {paciente.apellido}', 'Paciente', paciente.id)
    messages.success(request, f'Paciente {paciente.nombre} {paciente.apellido} ha sido {estado}.')
    return redirect('saldos_admin')

# LABORATORIO
@login_required
def resultados_laboratorio(request):
    """Lista de exámenes de laboratorio ya procesados con sus resultados."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Laboratorio').exists()):
        messages.error(request, 'No tienes permisos.')
        return redirect('home')
    
    q = request.GET.get('q', '').strip()
    resultados = SolicitudLaboratorio.objects.filter(
        estado='Procesado'
    ).select_related('paciente').order_by('-fecha_procesamiento')
    
    if q:
        resultados = resultados.filter(
            Q(paciente__nombre__icontains=q) | 
            Q(paciente__apellido__icontains=q) | 
            Q(paciente__cedula__icontains=q) |
            Q(prueba_laboratorio__icontains=q)
        )
    
    paginator = Paginator(resultados, 15)
    page = request.GET.get('page', 1)
    resultados = paginator.get_page(page)
    
    return render(request, 'ipp1/laboratorio/resultados_lab.html', {
        'resultados': resultados,
        'q': q,
    })