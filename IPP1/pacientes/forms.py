from .models import Paciente, SolicitudSecretaria, SolicitudLaboratorio, TarifaEspecialidad, Medicamento, Receta, PlanSalud, Poliza, GastoPaciente, Familiar
from django import forms
from django.contrib.auth.models import User

# LOGIN
class LoginForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese su usuario'}))
    password = forms.CharField(label='Contraseña', max_length=100, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese su contraseña'}))

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
    numero_telefono = forms.CharField(label='Número', max_length=7, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1234567', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57', 'inputmode': 'numeric'}))

    class Meta:
        model = Paciente
        fields = ['nombre', 'apellido', 'cedula', 'telefono', 'direccion', 'fecha_nacimiento']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese los nombres'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese los apellidos'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'V-12.345.678', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57', 'inputmode': 'numeric'}),
            'telefono': forms.HiddenInput(),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingresa la dirección completa'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_telefono'].widget.attrs.update({'class': 'form-control'})
        if self.instance and self.instance.telefono:
            raw = self.instance.telefono.strip()
            if len(raw) >= 4:
                self.fields['codigo_telefono'].initial = raw[:4]
                self.fields['numero_telefono'].initial = raw[4:]

    def clean(self):
        cleaned = super().clean()
        cod = cleaned.get('codigo_telefono', '')
        num = cleaned.get('numero_telefono', '')
        cleaned['telefono'] = f"{cod}{num}"
        return cleaned

# SOLICITUD DE CITA
class SolicitudSecretariaForm(forms.ModelForm):
    class Meta:
        model = SolicitudSecretaria
        fields = ['paciente', 'especialista', 'fecha_cita', 'hora_cita', 'motivo_consulta']
        widgets = {
            'fecha_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora_cita': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'motivo_consulta': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describa el motivo de la consulta...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paciente'].widget.attrs.update({'class': 'form-control'})
        self.fields['especialista'].widget.attrs.update({'class': 'form-control'})
        self.fields['especialista'].queryset = User.objects.filter(
            groups__name__in=['Medico', 'Odontologo', 'Especialista'],
            is_active=True
        )

# SOLICITUD DE LABORATORIO
class SolicitudLaboratorioForm(forms.ModelForm):
    class Meta:
        model = SolicitudLaboratorio
        fields = ['paciente', 'prueba_laboratorio', 'fecha_solicitud']
        widgets = {
            'paciente': forms.Select(attrs={'class': 'form-control'}),
            'prueba_laboratorio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Hemograma, Urianálisis, Perfil 20...'}),
            'fecha_solicitud': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

# PROCESAR LABORATORIO
class ProcesarLaboratorioForm(forms.ModelForm):
    class Meta:
        model = SolicitudLaboratorio
        fields = ['resultado', 'costo', 'bioanalista']
        widgets = {
            'resultado': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describa los resultados del examen...'}),
            'costo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'bioanalista': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del bioanalista'}),
        }

# TARIFA ESPECIALIDAD
class TarifaEspecialidadForm(forms.ModelForm):
    class Meta:
        model = TarifaEspecialidad
        fields = ['especialidad', 'costo_consulta', 'porcentaje_medico', 'descripcion']
        widgets = {
            'especialidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cardiología'}),
            'costo_consulta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'porcentaje_medico': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción del servicio...'}),
        }

# MEDICAMENTOS Y RECETAS
class MedicamentoForm(forms.ModelForm):
    class Meta:
        model = Medicamento
        fields = ['nombre', 'descripcion', 'precio', 'cantidad_stock', 'lote', 'fecha_vencimiento']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del medicamento'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción...'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cantidad_stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'lote': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de lote'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

# PLAN DE SALUD
class PlanSaludForm(forms.ModelForm):
    class Meta:
        model = PlanSalud
        fields = ['nombre', 'descripcion', 'costo_mensual', 'cobertura', 'consultas_maximas_anuales']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'costo_mensual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cobertura': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'consultas_maximas_anuales': forms.NumberInput(attrs={'class': 'form-control'}),
        }

# PÓLIZA
class PolizaForm(forms.ModelForm):
    class Meta:
        model = Poliza
        fields = ['paciente', 'plan', 'fecha_inicio', 'fecha_vencimiento', 'estado', 'saldo_restante']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'saldo_restante': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paciente'].widget.attrs.update({'class': 'form-control'})
        self.fields['plan'].widget.attrs.update({'class': 'form-control'})
        self.fields['estado'].widget.attrs.update({'class': 'form-control'})

# GASTO DEL PACIENTE
class GastoPacienteForm(forms.ModelForm):
    class Meta:
        model = GastoPaciente
        fields = ['concepto', 'monto', 'fecha', 'factura', 'beneficiario']
        widgets = {
            'concepto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Medicamentos'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'factura': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° de factura'}),
        }

    def __init__(self, *args, **kwargs):
        poliza_id = kwargs.pop('poliza_id', None)
        super().__init__(*args, **kwargs)
        self.fields['beneficiario'].widget.attrs.update({'class': 'form-control'})
        self.fields['beneficiario'].required = False
        if poliza_id:
            self.fields['beneficiario'].queryset = Familiar.objects.filter(poliza_id=poliza_id)
        elif self.instance and self.instance.poliza_id:
            self.fields['beneficiario'].queryset = Familiar.objects.filter(poliza_id=self.instance.poliza_id)

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
    parentesco = forms.ChoiceField(choices=PARENTESCO_CHOICES, label='Parentesco')

    class Meta:
        model = Familiar
        fields = ['nombre', 'apellido', 'cedula', 'parentesco', 'fecha_nacimiento']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

# RECETAS
class RecetaForm(forms.ModelForm):
    class Meta:
        model = Receta
        fields = ['medicamento', 'cantidad', 'dosis', 'duracion', 'indicaciones']
        widgets = {
            'medicamento': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'dosis': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1 tableta cada 8 horas'}),
            'duracion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 7 días'}),
            'indicaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Instrucciones adicionales...'}),
        }

