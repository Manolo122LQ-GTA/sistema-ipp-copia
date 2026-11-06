
# MODELOS IMPORTADOS

from .models import Paciente, SolicitudSecretaria, SolicitudLaboratorio, ExamenLaboratorio, TarifaEspecialidad, Medicamento, Receta, PlanSalud, Poliza, GastoPaciente, Familiar, TasaCambio
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
import re

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

# LOGIN

class LoginForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese su usuario'}))
    password = forms.CharField(label='Contraseña', max_length=100, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese su contraseña'}))

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
    codigo_telefono = forms.ChoiceField(choices=CODIGOS_TELEFONO_VE, label='Código')
    numero_telefono = forms.CharField(label='Número', max_length=7, widget=forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': '1234567', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57', 'inputmode': 'numeric'}))

# CATEGORIA DE AFILIADO
    class Meta:
        model = Paciente
        fields = ['nombre', 'apellido', 'cedula', 'telefono', 'direccion', 'fecha_nacimiento', 'status_afiliado', 'categoria_afiliado']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ingrese los nombres'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ingrese los apellidos'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'V-12.345.678', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57', 'inputmode': 'numeric'}),
            'telefono': forms.HiddenInput(),
            'direccion': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ingresa la dirección completa'}),
            'status_afiliado': forms.Select(attrs={'class': 'form-control uiverse-input'}),
            'categoria_afiliado': forms.Select(attrs={'class': 'form-control uiverse-input'}),
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

# NUMERO Y CODIGO DE TELEFONO SE UNEN PARA GUARDAR EN EL MODELO

    def clean(self):
        cleaned = super().clean()
        cod = cleaned.get('codigo_telefono', '')
        num = cleaned.get('numero_telefono', '')
        cleaned['telefono'] = f"{cod}{num}"
        return cleaned
# UN MIENTRAS TANTO
    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula', '')
        if not cedula:
            return cedula

        limpia = ''.join(c for c in str(cedula) if c.isdigit())
        if not limpia:
            raise forms.ValidationError('La cédula debe contener solo números.')
        if len(limpia) < 6 or len(limpia) > 8:
            raise forms.ValidationError('La cédula debe tener entre 6 y 8 dígitos.')

        self.cleaned_data['cedula'] = limpia
        if Paciente.objects.filter(cedula=limpia).exists():
            if not self.instance or self.instance.cedula != limpia:
                raise forms.ValidationError('Ya existe un paciente registrado con esta cédula.')
        return limpia

# UN MIENTRAS TANTO 2
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
            'costo': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'placeholder': '0.00', 'step': '0.01'}),
            'bioanalista': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Nombre del bioanalista'}),
        }

    def clean_costo(self):
        return _no_negativo(self.cleaned_data.get('costo'), 'El costo')

# TARIFA ESPECIALIDAD

class TarifaEspecialidadForm(forms.ModelForm):
    class Meta:
        model = TarifaEspecialidad
        fields = ['especialidad', 'costo_consulta', 'porcentaje_medico', 'descripcion']
        widgets = {
            'especialidad': forms.TextInput(attrs={'class': 'form-control uiverse-input', 'placeholder': 'Ej: Cardiología'}),
            'costo_consulta': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01'}),
            'porcentaje_medico': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01'}),
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
            'precio': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01'}),
            'cantidad_stock': forms.NumberInput(attrs={'class': 'form-control uiverse-input'}),
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
            'costo_mensual': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01'}),
            'cobertura': forms.Textarea(attrs={'class': 'form-control uiverse-input', 'rows': 3}),
            'servicios_maximos_anuales': forms.NumberInput(attrs={'class': 'form-control uiverse-input'}),
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
            'saldo_restante': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan'].required = True
        self.fields['paciente'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['plan'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['estado'].widget.attrs.update({'class': 'form-control uiverse-input'})
        self.fields['cuota_inicial'].widget.attrs.update({'class': 'form-control uiverse-input', 'step': '0.01'})
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
            'monto': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01'}),
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
            'nombre': forms.TextInput(attrs={'class': 'form-control uiverse-input'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control uiverse-input'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control uiverse-input'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control uiverse-input'}),
        }

    def clean_cedula(self):
        return _solo_digitos(self.cleaned_data.get('cedula'), 'La cédula')

# TASA DE CAMBIO

class TasaCambioForm(forms.ModelForm):
    class Meta:
        model = TasaCambio
        fields = ['tasa']
        widgets = {
            'tasa': forms.NumberInput(attrs={'class': 'form-control uiverse-input', 'step': '0.01', 'placeholder': 'Ej: 36.50'}),
        }

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