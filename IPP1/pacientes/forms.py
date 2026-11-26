# MODELOS IMPORTADOS
import re
from .models import Paciente, SolicitudSecretaria, SolicitudLaboratorio, ExamenLaboratorio, TarifaEspecialidad, Medicamento, Receta, PlanSalud, Poliza, GastoPaciente, Familiar, TasaCambio, Factura, PreguntaSeguridad, RespuestaSeguridad
from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from axes.models import AccessAttempt
from django.utils import timezone

class PasswordResetFormConError(PasswordResetForm):
    """Igual a la de Django, pero sin tragarse el error de envío.

    ``PasswordResetForm.send_mail()`` de Django 6 captura toda excepción y
    solo la escribe en el log, así que la vista siempre muestra "correo
    enviado" aunque SMTP haya fallado. Aquí se propaga para que la vista
    pueda avisar al usuario y registrar el contexto del error.
    """

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        mensaje = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html = loader.render_to_string(html_email_template_name, context)
            mensaje.attach_alternative(html, 'text/html')

        mensaje.send()


# VALIDACION PARA NO ESCRIBIR/USAR CORREO YA EXISTENTE EN "EDITAR PERFIL"


# VALIDACIONES 
def _no_negativo(valor, campo):
    if valor is not None and valor < 0:
        raise forms.ValidationError(f'{campo} no puede ser negativo.')
    return valor


# EL VALOR SOLO PUEDE SER NUMEROS
def _solo_digitos(valor, campo):
    if valor and not re.match(r'^\d+$', str(valor)):
        raise forms.ValidationError(f'{campo} debe contener solo números.')
    return valor


def _solo_letras(valor, campo, maximo=30):
    valor = ' '.join((valor or '').split())
    if not valor:
        return valor
    if len(valor) > maximo:
        raise forms.ValidationError(f'{campo} no puede superar {maximo} caracteres.')
    if not re.fullmatch(r'[A-Za-zÁÉÍÓÚÜáéíóúüÑñ ]+', valor):
        raise forms.ValidationError(f'{campo} solo puede contener letras y espacios.')
    return valor


MAX_LONGITUD_CONTRASENA = 128

ROLES_PERMITIDOS_REGISTRO = (
    'Secretaria', 'Medico', 'Odontologo', 'Laboratorio',
    'Especialista', 'Poliza', 'Administracion',
)


# REGISTRO PÚBLICO (antes se leía request.POST directo sin validar longitud/tipo)
class RegistroUsuarioForm(forms.Form):
    name = forms.CharField(label='Nombre', max_length=30, strip=True)
    last_name = forms.CharField(label='Apellido', max_length=30, strip=True)
    username = forms.CharField(
        label='Usuario', max_length=150, strip=True,
        validators=[UnicodeUsernameValidator()],
    )
    email = forms.EmailField(label='Correo', max_length=254, required=False)
    password = forms.CharField(
        label='Contraseña', widget=forms.PasswordInput,
        min_length=16,
    )
    password2 = forms.CharField(
        label='Confirmar contraseña', widget=forms.PasswordInput,
        min_length=16,
    )
    rol = forms.ChoiceField(
        label='Rol solicitado',
        choices=[('', 'Rol solicitado')] + [(r, r) for r in ROLES_PERMITIDOS_REGISTRO],
    )

    def clean_name(self):
        return _solo_letras(self.cleaned_data.get('name'), 'El nombre')

    def clean_last_name(self):
        return _solo_letras(self.cleaned_data.get('last_name'), 'El apellido')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ese nombre de usuario ya existe.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ese correo ya está registrado.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        password2 = cleaned.get('password2')
        if password and password2 and password != password2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        if password:
            candidato = User(
                username=cleaned.get('username', ''),
                email=cleaned.get('email', ''),
                first_name=cleaned.get('name', ''),
                last_name=cleaned.get('last_name', ''),
            )
            try:
                validate_password(password, user=candidato)
            except ValidationError as error:
                self.add_error('password', error.messages)
        return cleaned


# DESBLOQUEO DE CUENTAS (django-axes)
class GestionBloqueosForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=150, strip=True)

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and not AccessAttempt.objects.filter(username=username).exists():
            raise forms.ValidationError('No hay intentos registrados para ese usuario.')
        return username


# CATÁLOGO DE EXÁMENES (antes se armaba con request.POST.get)
class ExamenLaboratorioForm(forms.ModelForm):
    class Meta:
        model = ExamenLaboratorio
        fields = ['nombre', 'descripcion', 'costo']
        widgets = {
            'costo': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def clean_costo(self):
        return _no_negativo(self.cleaned_data.get('costo'), 'El costo')


# FACTURACIÓN
class FacturaGenerarForm(forms.Form):
    descripcion = forms.CharField(
        label='Descripción', required=False, max_length=500,
        widget=forms.Textarea(attrs={'rows': 3}),
    )


class MarcarPagoForm(forms.Form):
    metodo_pago = forms.ChoiceField(
        label='Método de pago',
        choices=[('', 'Seleccione un método')] + list(Factura.METODO_PAGO_CHOICES),
    )


# LOGIN
class LoginForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese su usuario'}))
    password = forms.CharField(label='Contraseña', strip=False, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese su contraseña'}))


# PERFIL DE USUARIO
class PerfilForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'maxlength': '30'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'maxlength': '150'}),
            'email': forms.EmailInput(attrs={'class': 'form-control uiverse-input', 'maxlength': '254'}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()

        # LOS CORREOS SON OPCIONALES, SI ESTA VACIO SE PUEDE GUARDAR
        if not email:
            return email

        # SE BUSCA EL MISMO CORREO EN OTROS USUARIOS
        otros = User.objects.filter(email__iexact=email)

        # SE EXCLUYE AL PROPIO USUARIO QUE ESTA EDITANDO SU PROPIO PERFIL
        if self.instance and self.instance.pk:
            otros = otros.exclude(pk=self.instance.pk)

        if otros.exists():
            raise forms.ValidationError(
                'Este correo ya está en uso por otro usuario'
            )

        return email


# PREGUNTAS DE SEGURIDAD EN EL PERFIL
class RespuestasSeguridadForm(forms.Form):
    """Actualiza las respuestas de seguridad del usuario autenticado.

    Los campos se generan desde el catálogo activo de preguntas. Las respuestas
    vacías se ignoran para permitir cambiar solo algunas sin borrar las demás.
    """

    password_actual = forms.CharField(
        label='Contraseña actual',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control uiverse-input',
            'autocomplete': 'current-password',
        }),
    )

    def __init__(self, *args, usuario=None, preguntas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.preguntas_por_campo = {}
        if preguntas is None:
            preguntas = PreguntaSeguridad.objects.filter(activa=True).order_by('orden')
        for pregunta in preguntas:
            nombre = f'respuesta_{pregunta.pk}'
            self.fields[nombre] = forms.CharField(
                label=pregunta.texto,
                required=False,
                max_length=128,
                widget=forms.PasswordInput(attrs={
                    'class': 'form-control uiverse-input',
                    'autocomplete': 'off',
                    'placeholder': 'Nueva respuesta',
                }),
            )
            self.preguntas_por_campo[nombre] = pregunta

    def clean_password_actual(self):
        password = self.cleaned_data.get('password_actual', '')
        if self.usuario is None or not self.usuario.check_password(password):
            raise ValidationError('La contraseña actual no es correcta.')
        return password

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        if not any(cleaned.get(nombre) for nombre in self.preguntas_por_campo):
            raise ValidationError('Escribe al menos una nueva respuesta.')
        return cleaned

    def save(self):
        """Guarda las respuestas escritas y devuelve cuántas se actualizaron."""
        actualizadas = 0
        for nombre, pregunta in self.preguntas_por_campo.items():
            respuesta = self.cleaned_data.get(nombre)
            if respuesta:
                RespuestaSeguridad.crear_o_actualizar(self.usuario, pregunta, respuesta)
                actualizadas += 1
        return actualizadas


class AdminPreguntasSeguridadForm(forms.Form):
    """Permite a Administración asignar 2 preguntas de seguridad y sus respuestas a un usuario."""

    pregunta_1 = forms.ModelChoiceField(
        label='Pregunta de seguridad 1',
        queryset=PreguntaSeguridad.objects.none(),
        empty_label='-- Seleccione la pregunta 1 --',
        widget=forms.Select(attrs={'class': 'form-select uiverse-input'}),
    )
    respuesta_1 = forms.CharField(
        label='Respuesta 1',
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control uiverse-input',
            'autocomplete': 'off',
            'placeholder': 'Respuesta para la pregunta 1',
        }),
    )
    pregunta_2 = forms.ModelChoiceField(
        label='Pregunta de seguridad 2',
        queryset=PreguntaSeguridad.objects.none(),
        empty_label='-- Seleccione la pregunta 2 --',
        widget=forms.Select(attrs={'class': 'form-select uiverse-input'}),
    )
    respuesta_2 = forms.CharField(
        label='Respuesta 2',
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control uiverse-input',
            'autocomplete': 'off',
            'placeholder': 'Respuesta para la pregunta 2',
        }),
    )
    reemplazar = forms.BooleanField(
        label='Reemplazar preguntas anteriores del usuario',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = PreguntaSeguridad.objects.filter(activa=True).order_by('orden', 'texto')
        self.fields['pregunta_1'].queryset = qs
        self.fields['pregunta_2'].queryset = qs

    def _limpiar_respuesta(self, campo):
        valor = (self.cleaned_data.get(campo) or '').strip()
        if not valor:
            raise ValidationError('La respuesta no puede estar vacía.')
        return valor

    def clean_respuesta_1(self):
        return self._limpiar_respuesta('respuesta_1')

    def clean_respuesta_2(self):
        return self._limpiar_respuesta('respuesta_2')

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('pregunta_1')
        p2 = cleaned.get('pregunta_2')
        if p1 and p2 and p1.pk == p2.pk:
            raise ValidationError('Debes seleccionar dos preguntas de seguridad diferentes.')
        return cleaned

    def save(self, usuario):
        """Guarda las 2 preguntas y respuestas hasheadas para el usuario indicado."""
        p1 = self.cleaned_data['pregunta_1']
        r1 = self.cleaned_data['respuesta_1']
        p2 = self.cleaned_data['pregunta_2']
        r2 = self.cleaned_data['respuesta_2']
        if self.cleaned_data.get('reemplazar'):
            RespuestaSeguridad.objects.filter(usuario=usuario).delete()
        RespuestaSeguridad.crear_o_actualizar(usuario, p1, r1)
        RespuestaSeguridad.crear_o_actualizar(usuario, p2, r2)

# CODIGOS DE TELEFONO VENEZOLANOS
CODIGOS_TELEFONO_VE = [
    ('0412', '0412'),
    ('0414', '0414'),
    ('0416', '0416'),
    ('0424', '0424'),
    ('0426', '0426'),
    ('0212', '0212 (Caracas)'),
    ('0241', '0241 (Valencia)'),
    ('0261', '0261 (Maracaibo)'),
    ('0268', '0268 (Coro)'),
]


# COSAS DE PACIENTES
class PacienteForm(forms.ModelForm):

# CODIGO & NUMERO DE TELEFONO SEPARADOS PARA FORMULARIO
    codigo_telefono = forms.ChoiceField(choices=CODIGOS_TELEFONO_VE, label='Código')
    numero_telefono = forms.CharField(label='Número', max_length=7, widget=forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': '1234567', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57', 'inputmode': 'numeric'}))
    
# CODIGO & NUMERO DE CEDULA SEPARADOS PARA FORMULARIO
    codigo_cedula = forms.ChoiceField(choices=[('V', 'V'), ('E', 'E'), ('P', 'P'), ('J', 'J'), ('G', 'G')], label='Código', required=False)
    numero_cedula = forms.CharField(
        label='Número', max_length=8, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control uiverse-input',
            'placeholder': '12345678',
            'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57',
            'inputmode': 'numeric',
        })
    )


# CATEGORIA DE AFILIADO
    class Meta:
        model = Paciente
        fields = ['nombre', 'apellido', 'telefono', 'direccion', 'fecha_nacimiento', 'status_afiliado', 'categoria_afiliado', 'codigo_cedula', 'numero_cedula']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'autocomplete': 'off', 'placeholder': 'Ingrese los nombres', 'pattern': '[A-Za-zÁÉÍÓÚáéíóúÑñ ]+', 'title': 'Solo se permiten letras y espacios', 'maxlength': '30'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'autocomplete': 'off', 'placeholder': 'Ingrese los apellidos', 'pattern': '[A-Za-zÁÉÍÓÚáéíóúÑñ ]+', 'title': 'Solo se permiten letras y espacios', 'maxlength': '30'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'V-12.345.678', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57', 'inputmode': 'numeric'}),
            'telefono': forms.HiddenInput(),
            'direccion': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'autocomplete': 'off', 'placeholder': 'Ingresa la dirección completa'}),
            'status_afiliado': forms.Select(attrs={'class': 'form-control uiverse-input'}),
            'categoria_afiliado': forms.Select(attrs={'class': 'form-control uiverse-input'}),
            'codigo_cedula': forms.Select(attrs={'class': 'form-control uiverse-input'}),
            'numero_cedula': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': '12345678', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57', 'inputmode': 'numeric'}),
        }

# CODIGO Y NUMERO DE TELEFONO SEPARADOS PARA FORMULARIO
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_telefono'].widget.attrs.update({'class': 'form-control uiverse-input'})
        if self.instance and self.instance.telefono:
            raw = self.instance.telefono.strip()
            if len(raw) >= 4:
                self.fields['codigo_telefono'].initial = raw[:4]
                self.fields['numero_telefono'].initial = raw[4:]
        if self.instance and self.instance.cedula:
            self.fields['codigo_cedula'].initial = 'V'
            self.fields['numero_cedula'].initial = ''.join(
                c for c in str(self.instance.cedula) if c.isdigit()
            )

    
# CEDULA VALIDACION: SOLO NUMEROS, ENTRE 6 Y 8 DIGITOS, UNICA EN LA BASE DE DATOS 
    # NOTA: no existe cleanup de `cedula` aquí porque `cedula` no es campo del
    # formulario (se compone desde codigo_cedula + numero_cedula en clean()).

# METODO CLEAN CODIGO NUMERO CEDULA
    def clean(self):
        cleaned = super().clean()
        numero = (cleaned.get('numero_cedula') or '').strip()

        if not numero:
            self.add_error('numero_cedula', 'La cédula es obligatoria.')
            return cleaned

        numero_limpio = ''.join(c for c in str(numero) if c.isdigit())
        if len(numero_limpio) < 6 or len(numero_limpio) > 8:
            self.add_error('numero_cedula', 'La cédula debe tener entre 6 y 8 dígitos.')
            return cleaned

        # El modelo almacena la cédula solo con dígitos (V/E/P/J/G es referencial)
        cleaned['cedula'] = numero_limpio
        existentes = Paciente.objects.filter(cedula=numero_limpio)
        if self.instance and self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            self.add_error('numero_cedula', 'Ya existe un paciente con esta cédula.')

        # El modelo guarda `telefono` como una sola cadena. Antes el campo
        # HiddenInput no se renderizaba y los campos separados se descartaban.
        codigo = (cleaned.get('codigo_telefono') or '').strip()
        numero_tel = (cleaned.get('numero_telefono') or '').strip()
        if codigo and numero_tel:
            if not re.fullmatch(r'\d+', numero_tel):
                self.add_error('numero_telefono', 'El teléfono debe contener solo números.')
            else:
                cleaned['telefono'] = f'{codigo}{numero_tel}'

        return cleaned

# LA CEDULA COMPUESTA SE ASIGNA AL MODELO ANTES DE GUARDAR
    def save(self, commit=True):
        paciente = super().save(commit=False)
        if self.cleaned_data.get('cedula'):
            paciente.cedula = self.cleaned_data['cedula']
        if commit:
            paciente.save()
            self.save_m2m()
        return paciente

# FECHA DE NACIMIENTO NO PUEDE SER FUTURA NI MAYOR A 120 AÑOS
    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if not fecha:
            return fecha
        from datetime import date
        if fecha > date.today():
            raise forms.ValidationError('La fecha de nacimiento no puede ser futura.')
        anios = (date.today() - fecha).days / 365.25
        if anios > 120:
            raise forms.ValidationError('La fecha de nacimiento parece incorrecta (¿más de 120 años?).')
        return fecha

# NOMBRE Y APELLIDO: SOLO LETRAS Y ESPACIOS
    def _validar_solo_letras(self, valor, campo):
        valor = ' '.join((valor or '').split())
        if not valor:
            return valor
        if not re.fullmatch(r'[A-Za-zÁÉÍÓÚÜáéíóúüÑñ ]+', valor):
            raise forms.ValidationError(
                f'{campo} solo puede contener letras y espacios.'
            )
        return valor

    def clean_nombre(self):
        return self._validar_solo_letras(self.cleaned_data.get('nombre'), 'El nombre')

    def clean_apellido(self):
        return self._validar_solo_letras(self.cleaned_data.get('apellido'), 'El apellido')


# CODIGOS DE IDENTIFICACION DE CEDULA VENEZOLANA (PACIENTFORM)
CODIGOS_CEDULA_VE = [
    'V',  # Venezolano
    'E',  # Extranjero
    'P',  # Pasaporte
    'J',  # Jurídico
    'G',  # Gobierno
]


# SOLICITUD DE CITA
def _tipo_paciente(paciente):
    partes = [paciente.status_afiliado]
    if paciente.categoria_afiliado and paciente.categoria_afiliado != 'Otro':
        partes.append(paciente.categoria_afiliado)
    return " - ".join(partes)


# MEDICO/ODONTOLOGO/ESPECIALISTA
def _especialista_label(usuario):
    grupo = usuario.groups.filter(name__in=['Medico', 'Odontologo', 'Especialista']).first()
    especialidad = grupo.name if grupo else 'Medico'
    nombre = usuario.last_name or usuario.username
    return f"{nombre} ({especialidad})"


# PACIENTE/ESPECIALISTA/FECHA/HORA/MOTIVO/CUANTOCOBRO/CUANTOCOBRA
class SolicitudSecretariaForm(forms.ModelForm):
    class Meta:
        model = SolicitudSecretaria
        fields = ['paciente', 'especialista', 'fecha_cita', 'hora_cita', 'motivo_consulta', 'cuanto_cobra', 'cuanto_cobro']
        labels = {
            'especialista': 'Médico Especialista',
            'motivo_consulta': 'Motivo de Solicitud',
            'cuanto_cobra': 'Monto a Cobrar',
            'cuanto_cobro': 'Monto Cobrado',
        }
        widgets = {
            'fecha_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
            'hora_cita': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control uiverse-input'}),
            'motivo_consulta': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 3, 'placeholder': 'Describa el motivo de la consulta...'}),
            'cuanto_cobra': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'}),
            'cuanto_cobro': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['paciente'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['especialista'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['especialista'].queryset = User.objects.filter(
            groups__name__in=['Medico', 'Odontologo', 'Especialista'],
            is_active=True
        ).distinct()
        self.fields['paciente'].label_from_instance = lambda obj: f"{obj.nombre} {obj.apellido} ({obj.cedula}) - {_tipo_paciente(obj)}"
        self.fields['especialista'].label_from_instance = _especialista_label
        self.fields['cuanto_cobra'].required = False
        self.fields['cuanto_cobro'].required = False
        beneficiario = self.initial.get('beneficiario')
        if beneficiario:
            self.fields['paciente'].initial = beneficiario.poliza.paciente.id
            self.fields['beneficiario'].initial = beneficiario.id

        # Si el usuario actual es Medico (y no Secretaria), bloquear el especialista a sí mismo
        if self.current_user and self.current_user.groups.filter(name='Medico').exists() and not self.current_user.is_superuser:
            self.fields['especialista'].initial = self.current_user
            self.fields['especialista'].widget.attrs['readonly'] = True
            self.fields['especialista'].widget.attrs['disabled'] = True


# HACER QUE LA FECHA NO PUEDA SER LA MISMA DEL MISMO DIA DEL HOY
    def clean_fecha_cita(self):
        fecha = self.cleaned_data.get('fecha_cita')
        if fecha and fecha < timezone.now().date():
            raise forms.ValidationError('La fecha de la cita no puede ser en el pasado.')
        return fecha


# IMPEDIR DOBLE RESERVA DEL MISMO ESPECIALISTA EN LA MISMA FECHA Y HORA
    def clean(self):
        cleaned_data = super().clean()
        especialista = cleaned_data.get('especialista')
        fecha_cita = cleaned_data.get('fecha_cita')
        hora_cita = cleaned_data.get('hora_cita')
        if especialista and fecha_cita and hora_cita:
            if SolicitudSecretaria.objects.filter(
                especialista=especialista,
                fecha_cita=fecha_cita,
                hora_cita=hora_cita,
                estado__in=['En Espera', 'Atendido'],
            ).exists():
                raise forms.ValidationError('El especialista ya tiene una cita programada para esa fecha y hora.')
        return cleaned_data


# SOLICITUD DE LABORATORIO
class SolicitudLaboratorioForm(forms.ModelForm):
    class Meta:
        model = SolicitudLaboratorio
        fields = ['paciente', 'examen', 'fecha_solicitud']
        widgets = {
            'paciente': forms.Select(attrs={'class': 'form-control uiverse-input'}),
            'examen': forms.Select(attrs={'class': 'form-control uiverse-input', 'id': 'id_examen'}),
            'fecha_solicitud': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        examen = cleaned.get('examen')
        prueba = cleaned.get('prueba_laboratorio')
        if examen and not prueba:
            cleaned['prueba_laboratorio'] = examen.nombre
        if not examen and not cleaned.get('prueba_laboratorio'):
            self.add_error('examen', 'Seleccione un examen del catálogo.')
        return cleaned


# PROCESAR LABORATORIO
class ProcesarLaboratorioForm(forms.ModelForm):
    class Meta:
        model = SolicitudLaboratorio
        fields = ['resultado', 'costo', 'bioanalista']
        widgets = {
            'resultado': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 4, 'placeholder': 'Describa los resultados del examen...'}),
            'costo': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'bioanalista': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'maxlength': '100', 'placeholder': 'Nombre del bioanalista'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resultado'].required = True

    def clean_costo(self):
        return _no_negativo(self.cleaned_data.get('costo'), 'El costo')


# TARIFA ESPECIALIDAD
class TarifaEspecialidadForm(forms.ModelForm):
    class Meta:
        model = TarifaEspecialidad
        fields = ['especialidad', 'costo_consulta', 'porcentaje_medico', 'descripcion']
        widgets = {
            'especialidad': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ej: Cardiología'}),
            'costo_consulta': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'}),
            'porcentaje_medico': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0', 'max': '100'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 3, 'placeholder': 'Descripción del servicio...'}),
        }

    def clean_costo_consulta(self):
        return _no_negativo(self.cleaned_data.get('costo_consulta'), 'El costo de consulta')

    def clean_porcentaje_medico(self):
        valor = self.cleaned_data.get('porcentaje_medico')
        if valor is None:
            return valor
        if valor < 0 or valor > 100:
            raise forms.ValidationError('El porcentaje del médico debe estar entre 0 y 100.')
        return valor


# MEDICAMENTOS Y RECETAS
class MedicamentoForm(forms.ModelForm):
    class Meta:
        model = Medicamento
        fields = ['nombre', 'descripcion', 'precio', 'cantidad_stock', 'lote', 'fecha_vencimiento']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Nombre del medicamento'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 2, 'placeholder': 'Descripción...'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'}),
            'cantidad_stock': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'min': '0'}),
            'lote': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Número de lote'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
        }

    def clean_precio(self):
        return _no_negativo(self.cleaned_data.get('precio'), 'El precio')

    def clean_cantidad_stock(self):
        return _no_negativo(self.cleaned_data.get('cantidad_stock'), 'La cantidad en stock')


# PLAN DE SALUD
class PlanSaludForm(forms.ModelForm):
    class Meta:
        model = PlanSalud
        fields = ['nombre', 'descripcion', 'costo_mensual', 'cobertura', 'servicios_maximos_anuales']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control uiverse-input'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 3}),
            'costo_mensual': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'}),
            'cobertura': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 3}),
            'servicios_maximos_anuales': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'min': '0'}),
        }

    def clean_costo_mensual(self):
        return _no_negativo(self.cleaned_data.get('costo_mensual'), 'El costo mensual')

    def clean_servicios_maximos_anuales(self):
        return _no_negativo(self.cleaned_data.get('servicios_maximos_anuales'), 'Los servicios máximos')

# PÓLIZA
class PolizaForm(forms.ModelForm):
    class Meta:
        model = Poliza
        fields = ['paciente', 'plan', 'fecha_inicio', 'fecha_vencimiento', 'estado', 'cuota_inicial', 'saldo_restante']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
            'saldo_restante': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan'].required = True
        self.fields['paciente'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['plan'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['estado'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['cuota_inicial'].widget.attrs.update({'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'})
        if not self.instance.pk:
            # Para póliza nueva: saldo_restante visible y editable (plan único)
            self.fields['saldo_restante'].required = True
            self.fields['cuota_inicial'].required = True
            self.fields['saldo_restante'].help_text = "Saldo restante inicial (ej: $100.00)"
            self.fields['cuota_inicial'].help_text = "Cuota inicial pagada (ej: $100.00)"
        else:
            self.fields['cuota_inicial'].widget = forms.HiddenInput()
            self.fields['saldo_restante'].disabled = True

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get('plan')
        cuota = cleaned.get('cuota_inicial')
        saldo = cleaned.get('saldo_restante')
        if plan and cuota is not None and cuota > plan.costo_mensual:
            self.add_error(
                'cuota_inicial',
                'La cuota inicial no puede superar el costo mensual del plan.'
            )
        if cuota is not None and cuota < 0:
            self.add_error('cuota_inicial', 'La cuota inicial no puede ser negativa.')
        if saldo is not None and saldo < 0:
            self.add_error('saldo_restante', 'El saldo restante no puede ser negativo.')
        return cleaned

# GASTO DEL PACIENTE
class GastoPacienteForm(forms.ModelForm):
    class Meta:
        model = GastoPaciente
        fields = ['concepto', 'monto', 'fecha', 'factura', 'beneficiario']
        widgets = {
            'concepto': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ej: Medicamentos'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0'}),
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
            'factura': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'N° de factura'}),
        }

    def __init__(self, *args, **kwargs):
        poliza_id = kwargs.pop('poliza_id', None)
        super().__init__(*args, **kwargs)
        self.fields['beneficiario'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['beneficiario'].required = False
        if poliza_id:
            self.fields['beneficiario'].queryset = Familiar.objects.filter(poliza_id=poliza_id)
        elif self.instance and self.instance.poliza_id:
            self.fields['beneficiario'].queryset = Familiar.objects.filter(poliza_id=self.instance.poliza_id)

    def clean_monto(self):
        return _no_negativo(self.cleaned_data.get('monto'), 'El monto')

# FAMILIAR
class FamiliarForm(forms.ModelForm):
    PARENTESCO_CHOICES = [
        ('Cónyuge', 'Cónyuge'),
        ('Hijo(a)', 'Hijo(a)'),
        ('Padre', 'Padre'),
        ('Madre', 'Madre'),
        ('Hermano(a)', 'Hermano(a)'),
        ('Otro', 'Otro'),
    ]
    parentesco = forms.ChoiceField(choices=PARENTESCO_CHOICES, label='Parentesco', widget=forms.Select(attrs={'class': 'form-control uiverse-input'}))

    class Meta:
        model = Familiar
        fields = ['nombre', 'apellido', 'cedula', 'parentesco', 'fecha_nacimiento']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'autocomplete': 'off'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'autocomplete': 'off'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control uiverse-input'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
        }

    def clean_cedula(self):
        cedula = _solo_digitos(self.cleaned_data.get('cedula'), 'La cédula')
        if cedula and not (6 <= len(cedula) <= 10):
            raise forms.ValidationError('La cédula debe tener entre 6 y 10 dígitos.')
        return cedula

# TASA DE CAMBIO
class TasaCambioForm(forms.ModelForm):
    class Meta:
        model = TasaCambio
        fields = ['tasa']
        widgets = {
            'tasa': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'min': '0', 'placeholder': 'Ej: 36.50'}),
        }

    def clean_tasa(self):
        return _no_negativo(self.cleaned_data.get('tasa'), 'La tasa')

# RECETAS
class RecetaForm(forms.ModelForm):
    class Meta:
        model = Receta
        fields = ['medicamento', 'examen', 'cantidad', 'dosis', 'duracion', 'indicaciones']
        widgets = {
            'medicamento': forms.Select(attrs={'class': 'form-control uiverse-input', 'id': 'id_medicamento'}),
            'examen': forms.Select(attrs={'class': 'form-control uiverse-input', 'id': 'id_examen_receta'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'min': '1'}),
            'dosis': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ej: 1 tableta cada 8 horas'}),
            'duracion': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ej: 7 días'}),
            'indicaciones': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 3, 'placeholder': 'Instrucciones adicionales...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medicamento'].queryset = Medicamento.objects.filter(activo=True)
        self.fields['examen'].queryset = ExamenLaboratorio.objects.filter(activo=True)
        self.fields['medicamento'].required = False
        self.fields['examen'].required = False

    def clean(self):
        cleaned = super().clean()
        medicamento = cleaned.get('medicamento')
        examen = cleaned.get('examen')
        if not medicamento and not examen:
            raise forms.ValidationError('Debe seleccionar al menos un medicamento o un examen de laboratorio.')
        return cleaned

    def clean_cantidad(self):
        valor = self.cleaned_data.get('cantidad')
        if valor is not None and valor < 1:
            raise forms.ValidationError('La cantidad debe ser al menos 1.')
        return valor

# REFINAMIENTO DE CITA
class SolicitudSecretariaRefinarForm(forms.ModelForm):
    """Formulario para reprogramar (refinar) fecha y hora de una cita pendiente."""
    class Meta:
        model = SolicitudSecretaria
        fields = ['fecha_cita', 'hora_cita']
        widgets = {
            'fecha_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
            'hora_cita': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control uiverse-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_fecha_cita(self):
        fecha = self.cleaned_data.get('fecha_cita')
        if fecha and fecha < timezone.now().date():
            raise forms.ValidationError('La fecha de la cita no puede ser en el pasado.')
        return fecha

    def clean(self):
        cleaned_data = super().clean()
        especialista = self.instance.especialista
        fecha_cita = cleaned_data.get('fecha_cita')
        hora_cita = cleaned_data.get('hora_cita')
        if especialista and fecha_cita and hora_cita:
            if SolicitudSecretaria.objects.filter(
                especialista=especialista,
                fecha_cita=fecha_cita,
                hora_cita=hora_cita,
                estado__in=['En Espera', 'Atendido'],
            ).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError('El especialista ya tiene una cita programada para esa fecha y hora.')
        return cleaned_data


class ConfirmarPasswordAdminForm(forms.Form):
    """Solicita la contraseña actual del operador para confirmar acciones críticas."""

    password_admin = forms.CharField(
        label='Contraseña actual del administrador',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control uiverse-input',
            'autocomplete': 'current-password',
            'placeholder': 'Ingresa tu contraseña para confirmar',
        }),
    )

    def __init__(self, *args, operador=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.operador = operador

    def clean_password_admin(self):
        password = self.cleaned_data.get('password_admin', '')
        if self.operador is None or not self.operador.check_password(password):
            raise ValidationError('La contraseña ingresada es incorrecta.')
        return password


class Verificar2FAForm(forms.Form):
    """Código OTP de 6 dígitos enviado al correo para segundo factor de autenticación."""

    codigo = forms.CharField(
        label='Código de verificación',
        max_length=12,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control uiverse-input text-center fw-bold',
            'placeholder': 'Ej: 123456',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
        }),
    )

    def clean_codigo(self):
        codigo = re.sub(r'[^0-9]', '', self.cleaned_data.get('codigo', ''))
        if len(codigo) != 6:
            raise ValidationError('Ingresa el código numérico de 6 dígitos.')
        return codigo

