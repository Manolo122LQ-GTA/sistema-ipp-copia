from decimal import Decimal
from datetime import date, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from .models import (
    Paciente, SolicitudSecretaria, SolicitudLaboratorio,
    PlanSalud, Poliza, GastoPaciente, Familiar,
    TarifaEspecialidad, Medicamento, Receta, Factura
)
from .forms import (
    LoginForm, PacienteForm, SolicitudSecretariaForm,
    SolicitudLaboratorioForm, ProcesarLaboratorioForm,
    TarifaEspecialidadForm, MedicamentoForm
)
from .validators import ValidarContrasenaFuerte


# ===================== HELPERS =====================

class BaseTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.validator = ValidarContrasenaFuerte()
        self._crear_grupos()

    def _crear_grupos(self):
        for nombre in ['Secretaria', 'Medico', 'Odontologo', 'Especialista', 'Laboratorio', 'Administracion']:
            Group.objects.get_or_create(name=nombre)

    def _crear_usuario(self, username='testuser', password='Test1234!', grupo=None):
        user = User.objects.create_user(username=username, password=password)
        if grupo:
            user.groups.add(Group.objects.get(name=grupo))
        return user

    def _login(self, grupo=None):
        user = self._crear_usuario(grupo=grupo)
        self.client.force_login(user)
        return user

    def _crear_paciente(self, **kwargs):
        defaults = {
            'nombre': 'Juan', 'apellido': 'Perez', 'cedula': '12345678',
            'fecha_nacimiento': date(1990, 5, 15),
        }
        defaults.update(kwargs)
        return Paciente.objects.create(**defaults)


# ===================== MODEL TESTS =====================

class PacienteModelTest(BaseTest):
    def test_creacion_paciente(self):
        p = self._crear_paciente()
        self.assertEqual(p.nombre, 'Juan')
        self.assertEqual(p.apellido, 'Perez')
        self.assertEqual(p.cedula, '12345678')
        self.assertEqual(p.status_afiliado, 'Comunidad')
        self.assertEqual(p.saldo_plan_salud, Decimal('0.00'))

    def test_str_representation(self):
        p = self._crear_paciente()
        self.assertEqual(str(p), 'Juan Perez (12345678)')

    def test_cedula_unica(self):
        self._crear_paciente(cedula='12345678')
        with self.assertRaises(Exception):
            self._crear_paciente(cedula='12345678', nombre='Otro')

    def test_status_choices(self):
        p = self._crear_paciente(status_afiliado='Afiliado')
        self.assertEqual(p.status_afiliado, 'Afiliado')
        p2 = self._crear_paciente(cedula='87654321', status_afiliado='Comunidad')
        self.assertEqual(p2.status_afiliado, 'Comunidad')


class SolicitudSecretariaModelTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()
        self.especialista = self._crear_usuario('dr', 'Test1234!', 'Medico')

    def test_creacion_solicitud(self):
        s = SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.especialista,
            fecha_cita=date(2026, 7, 10), hora_cita=time(10, 30),
            motivo_consulta='Dolor de cabeza'
        )
        self.assertEqual(s.estado, 'En Espera')
        self.assertFalse(s.cobro_nomina)
        self.assertIn('Juan', str(s))

    def test_estado_choices(self):
        s = SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.especialista,
            fecha_cita=date(2026, 7, 10), hora_cita=time(10, 30),
            estado='Atendido'
        )
        self.assertEqual(s.estado, 'Atendido')

    def test_cascade_delete_paciente(self):
        SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.especialista,
            fecha_cita=date(2026, 7, 10), hora_cita=time(10, 30),
        )
        self.assertEqual(SolicitudSecretaria.objects.count(), 1)
        self.paciente.delete()
        self.assertEqual(SolicitudSecretaria.objects.count(), 0)


class SolicitudLaboratorioModelTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()

    def test_creacion(self):
        s = SolicitudLaboratorio.objects.create(
            paciente=self.paciente, prueba_laboratorio='Hemograma',
            fecha_solicitud=date(2026, 7, 5)
        )
        self.assertEqual(s.estado, 'Pendiente')
        self.assertEqual(s.costo, Decimal('0.00'))
        self.assertIn('Hemograma', str(s))


class PlanSaludModelTest(BaseTest):
    def test_creacion(self):
        plan = PlanSalud.objects.create(
            nombre='Plan Básico', costo_mensual=Decimal('25.00'),
            descripcion='Cobertura básica'
        )
        self.assertEqual(str(plan), 'Plan Básico - $25.00/mes (4 consultas/año)')
        self.assertEqual(plan.consultas_maximas_anuales, 4)


class PolizaModelTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()
        self.plan = PlanSalud.objects.create(nombre='Plan Básico', costo_mensual=Decimal('25.00'))

    def test_creacion_poliza(self):
        p = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1), saldo_restante=Decimal('500.00')
        )
        self.assertEqual(p.estado, 'Activo')
        self.assertEqual(p.saldo_restante, Decimal('500.00'))

    def test_str_representation(self):
        p = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1)
        )
        self.assertIn('Juan', str(p))

    def test_consultas_usadas_anuales_sin_citas(self):
        p = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1)
        )
        self.assertEqual(p.consultas_usadas_anuales(), 0)

    def test_consultas_restantes_con_limite(self):
        self.plan.consultas_maximas_anuales = 4
        self.plan.save()
        p = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1)
        )
        self.assertEqual(p.consultas_restantes(), 4)

    def test_consultas_restantes_ilimitado(self):
        self.plan.consultas_maximas_anuales = 0
        self.plan.save()
        p = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1)
        )
        self.assertIsNone(p.consultas_restantes())

    def test_consultas_usadas_anuales_cuenta_citas(self):
        medico = self._crear_usuario('dr_cons', 'Test1234!', 'Medico')
        p = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1)
        )
        SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=medico,
            fecha_cita=date(2026, 6, 1), hora_cita=time(10, 0),
            cubierto_por_poliza=True, poliza=p, estado='Atendido'
        )
        self.assertEqual(p.consultas_usadas_anuales(), 1)

    def test_consultas_restantes_agotado(self):
        self.plan.consultas_maximas_anuales = 1
        self.plan.save()
        medico = self._crear_usuario('dr_cons2', 'Test1234!', 'Medico')
        p = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1)
        )
        SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=medico,
            fecha_cita=date(2026, 6, 1), hora_cita=time(10, 0),
            cubierto_por_poliza=True, poliza=p, estado='Atendido'
        )
        self.assertEqual(p.consultas_restantes(), 0)


class GastoPacienteModelTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()
        self.plan = PlanSalud.objects.create(nombre='Plan Básico', costo_mensual=Decimal('25.00'))
        self.poliza = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1), saldo_restante=Decimal('500.00')
        )

    def test_creacion_gasto(self):
        g = GastoPaciente.objects.create(
            poliza=self.poliza, concepto='Consulta',
            monto=Decimal('50.00'), fecha=date(2026, 6, 1)
        )
        self.assertEqual(str(g), 'Consulta - $50.00 (Juan Perez (12345678))')


class FamiliarModelTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()
        self.plan = PlanSalud.objects.create(nombre='Plan Básico', costo_mensual=Decimal('25.00'))
        self.poliza = Poliza.objects.create(paciente=self.paciente, plan=self.plan, fecha_inicio=date(2026, 1, 1))

    def test_creacion_familiar(self):
        f = Familiar.objects.create(
            poliza=self.poliza, nombre='Ana', apellido='Perez',
            cedula='1234567', parentesco='Cónyuge',
            fecha_nacimiento=date(1992, 3, 10)
        )
        self.assertEqual(str(f), 'Ana Perez (Cónyuge)')


class TarifaEspecialidadModelTest(BaseTest):
    def test_creacion(self):
        t = TarifaEspecialidad.objects.create(
            especialidad='Cardiología', costo_consulta=Decimal('80.00'),
            descripcion='Consulta cardiológica'
        )
        self.assertEqual(str(t), 'Cardiología - $80.00')
        self.assertTrue(t.activo)


class MedicamentoModelTest(BaseTest):
    def test_creacion(self):
        m = Medicamento.objects.create(
            nombre='Paracetamol', precio=Decimal('5.00'),
            cantidad_stock=100, lote='LOT001',
            fecha_vencimiento=date(2027, 12, 31)
        )
        self.assertEqual(str(m), 'Paracetamol (stock: 100)')
        self.assertTrue(m.activo)


# ===================== VALIDATOR TESTS =====================

class ValidatorTest(BaseTest):
    def test_valida_password_valido(self):
        try:
            self.validator.validate('Abcd1234!')
        except ValidationError:
            self.fail('Password válido lanzó ValidationError')

    def test_rechaza_corto(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('Ab1!')
        self.assertIn('8 caracteres', str(ctx.exception))

    def test_rechaza_sin_mayuscula(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('abcd1234!')
        self.assertIn('mayúscula', str(ctx.exception))

    def test_rechaza_sin_minuscula(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('ABCD1234!')
        self.assertIn('minúscula', str(ctx.exception))

    def test_rechaza_sin_numero(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('Abcdefgh!')
        self.assertIn('número', str(ctx.exception))

    def test_rechaza_sin_especial(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('Abcdefgh1')
        self.assertIn('especial', str(ctx.exception))

    def test_help_text(self):
        texto = self.validator.get_help_text()
        self.assertIn('8 caracteres', texto)
        self.assertIn('minúscula', texto)
        self.assertIn('mayúscula', texto)
        self.assertIn('número', texto)
        self.assertIn('especial', texto)


# ===================== FORM TESTS =====================

class LoginFormTest(BaseTest):
    def test_form_valido(self):
        form = LoginForm(data={'username': 'test', 'password': 'pass'})
        self.assertTrue(form.is_valid())

    def test_campos_requeridos(self):
        form = LoginForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn('password', form.errors)


class PacienteFormTest(BaseTest):
    def test_form_valido(self):
        form = PacienteForm(data={
            'nombre': 'Juan', 'apellido': 'Perez', 'cedula': '12345678',
            'codigo_telefono': '0412', 'numero_telefono': '1234567',
            'fecha_nacimiento': '1990-05-15',
            'status_afiliado': 'Afiliado', 'categoria_afiliado': 'Docente',
        })
        self.assertTrue(form.is_valid())

    def test_campos_requeridos(self):
        form = PacienteForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('apellido', form.errors)
        self.assertIn('cedula', form.errors)
        self.assertIn('fecha_nacimiento', form.errors)

    def test_cedula_unica(self):
        self._crear_paciente(cedula='12345678')
        form = PacienteForm(data={
            'nombre': 'Otro', 'apellido': 'Perez', 'cedula': '12345678',
            'codigo_telefono': '0412', 'numero_telefono': '1234567',
            'fecha_nacimiento': '1990-05-15',
            'status_afiliado': 'Afiliado', 'categoria_afiliado': 'Beneficiario',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('cedula', form.errors)


class SolicitudSecretariaFormTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()
        self.medico = self._crear_usuario('dr_medico', 'Test1234!', 'Medico')

    def test_form_valido(self):
        form = SolicitudSecretariaForm(data={
            'paciente': self.paciente.id,
            'especialista': self.medico.id,
            'fecha_cita': '2026-07-15',
            'hora_cita': '14:30',
            'motivo_consulta': 'Control'
        })
        self.assertTrue(form.is_valid())

    def test_especialista_queryset_filtrado(self):
        odontologo = self._crear_usuario('dr_odon', 'Test1234!', 'Odontologo')
        self._crear_usuario('solo_user', 'Test1234!')
        form = SolicitudSecretariaForm()
        qs = form.fields['especialista'].queryset
        self.assertIn(self.medico, qs)
        self.assertIn(odontologo, qs)
        self.assertNotIn(User.objects.get(username='solo_user'), qs)


class SolicitudLaboratorioFormTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()

    def test_form_valido(self):
        form = SolicitudLaboratorioForm(data={
            'paciente': self.paciente.id,
            'prueba_laboratorio': 'Hemograma',
            'fecha_solicitud': '2026-07-05'
        })
        self.assertTrue(form.is_valid())

    def test_campos_requeridos(self):
        form = SolicitudLaboratorioForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('paciente', form.errors)
        self.assertIn('prueba_laboratorio', form.errors)


class ProcesarLaboratorioFormTest(BaseTest):
    def test_form_valido(self):
        form = ProcesarLaboratorioForm(data={
            'resultado': 'Normal', 'costo': '25.00', 'bioanalista': 'Dr. Lopez'
        })
        self.assertTrue(form.is_valid())


class TarifaEspecialidadFormTest(BaseTest):
    def test_form_valido(self):
        form = TarifaEspecialidadForm(data={
            'especialidad': 'Cardiología', 'costo_consulta': '80.00', 'porcentaje_medico': '50.00'
        })
        self.assertTrue(form.is_valid())

    def test_especialidad_unica(self):
        TarifaEspecialidad.objects.create(especialidad='Cardiología', costo_consulta=Decimal('80.00'))
        form = TarifaEspecialidadForm(data={
            'especialidad': 'Cardiología', 'costo_consulta': '90.00', 'porcentaje_medico': '50.00'
        })
        self.assertFalse(form.is_valid())


class MedicamentoFormTest(BaseTest):
    def test_form_valido(self):
        form = MedicamentoForm(data={
            'nombre': 'Paracetamol', 'precio': '5.00',
            'cantidad_stock': '100'
        })
        self.assertTrue(form.is_valid())


# ===================== VIEW TESTS =====================

class LoginViewTest(BaseTest):
    def test_login_page_carga(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ipp1/compartidos/login.html')

    def test_login_redirect_si_autenticado(self):
        self._login()
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'))

    def test_login_valido(self):
        self._crear_usuario()
        response = self.client.post(reverse('login'), {
            'username': 'testuser', 'password': 'Test1234!'
        })
        self.assertRedirects(response, reverse('home'))

    def test_login_usuario_no_existe(self):
        response = self.client.post(reverse('login'), {
            'username': 'noexiste', 'password': 'Test1234!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no existe')

    def test_login_password_incorrecto(self):
        self._crear_usuario()
        response = self.client.post(reverse('login'), {
            'username': 'testuser', 'password': 'WrongPass1!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'incorrecta')


class LogoutViewTest(BaseTest):
    def test_logout_requiere_post(self):
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)

    def test_logout_valido(self):
        self._login()
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))


class RegistroViewTest(BaseTest):
    def test_registro_page_carga(self):
        response = self.client.get(reverse('registro'))
        self.assertEqual(response.status_code, 200)

    def test_registro_valido(self):
        response = self.client.post(reverse('registro'), {
            'username': 'nuevousuario',
            'password': 'Abc123!@',
            'name': 'Carlos',
            'last_name': 'Lopez',
            'email': 'carlos@test.com',
            'rol': 'Medico'
        })
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(username='nuevousuario').exists())
        user = User.objects.get(username='nuevousuario')
        self.assertTrue(user.groups.filter(name='Medico').exists())

    def test_registro_usuario_duplicado(self):
        self._crear_usuario(username='existente')
        response = self.client.post(reverse('registro'), {
            'username': 'existente', 'password': 'Abc123!@'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ya existe')

    def test_registro_password_debil(self):
        response = self.client.post(reverse('registro'), {
            'username': 'nuevo', 'password': 'corta'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '8 caracteres')


class AccessControlTest(BaseTest):
    """Prueba que cada vista rechace acceso sin permiso."""

    def test_secretaria_sin_login_redirect(self):
        for url_name in ['secretaria', 'registrar_paciente', 'crear_solicitud']:
            response = self.client.get(reverse(url_name))
            self.assertNotEqual(response.status_code, 200, f'{url_name} debería redirigir')

    def test_secretaria_denegado_sin_rol(self):
        self._login()
        response = self.client.get(reverse('secretaria'))
        self.assertRedirects(response, reverse('home'))

    def test_secretaria_acceso_valido(self):
        self._login(grupo='Secretaria')
        response = self.client.get(reverse('secretaria'))
        self.assertEqual(response.status_code, 200)

    def test_medico_denegado_sin_rol(self):
        self._login()
        response = self.client.get(reverse('medico_panel'))
        self.assertRedirects(response, reverse('home'))

    def test_medico_acceso_valido(self):
        self._login(grupo='Medico')
        response = self.client.get(reverse('medico_panel'))
        self.assertEqual(response.status_code, 200)

    def test_odontologo_denegado_sin_rol(self):
        self._login()
        response = self.client.get(reverse('odontologo'))
        self.assertRedirects(response, reverse('home'))

    def test_odontologo_acceso_valido(self):
        self._login(grupo='Odontologo')
        response = self.client.get(reverse('odontologo'))
        self.assertEqual(response.status_code, 200)

    def test_admin_denegado_sin_rol(self):
        self._login()
        response = self.client.get(reverse('inicio_admin'))
        self.assertRedirects(response, reverse('home'))

    def test_admin_acceso_valido(self):
        self._login(grupo='Administracion')
        response = self.client.get(reverse('inicio_admin'))
        self.assertEqual(response.status_code, 200)


class CitaFlowTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()
        self.medico = self._crear_usuario('dr_medico', 'Test1234!', 'Medico')
        self.odontologo = self._crear_usuario('dr_odonto', 'Test1234!', 'Odontologo')

    def test_crear_solicitud(self):
        self._login(grupo='Secretaria')
        response = self.client.post(reverse('crear_solicitud'), {
            'paciente': self.paciente.id,
            'especialista': self.medico.id,
            'fecha_cita': '2026-07-20',
            'hora_cita': '09:00',
            'motivo_consulta': 'Control general'
        }, follow=True)
        self.assertContains(response, 'exitosamente')
        self.assertEqual(SolicitudSecretaria.objects.count(), 1)

    def test_atender_cita_requiere_post(self):
        cita = SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.medico,
            fecha_cita=date(2026, 7, 20), hora_cita=time(9, 0)
        )
        self._login(grupo='Medico')
        response = self.client.get(reverse('atender_cita', args=[cita.id]))
        self.assertEqual(response.status_code, 405)

    def test_atender_cita_valido(self):
        cita = SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.medico,
            fecha_cita=date(2026, 7, 20), hora_cita=time(9, 0)
        )
        self.client.force_login(self.medico)
        response = self.client.post(reverse('atender_cita', args=[cita.id]))
        self.assertRedirects(response, reverse('citas_recibidas_medico'))
        cita.refresh_from_db()
        self.assertEqual(cita.estado, 'Atendido')

    def test_cancelar_cita_valido(self):
        cita = SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.medico,
            fecha_cita=date(2026, 7, 20), hora_cita=time(9, 0)
        )
        self.client.force_login(self.medico)
        response = self.client.post(reverse('cancelar_cita', args=[cita.id]))
        self.assertRedirects(response, reverse('citas_recibidas_medico'))
        cita.refresh_from_db()
        self.assertEqual(cita.estado, 'Cancelado')

    def test_crear_solicitud_con_poliza_cubre_cita(self):
        plan = PlanSalud.objects.create(nombre='Test', costo_mensual=Decimal('10'), consultas_maximas_anuales=4)
        Poliza.objects.create(
            paciente=self.paciente, plan=plan,
            fecha_inicio=date(2026, 1, 1), estado='Activo'
        )
        self._login(grupo='Secretaria')
        response = self.client.post(reverse('crear_solicitud'), {
            'paciente': self.paciente.id,
            'especialista': self.odontologo.id,
            'fecha_cita': '2026-07-20',
            'hora_cita': '09:00',
        }, follow=True)
        self.assertContains(response, 'exitosamente')
        cita = SolicitudSecretaria.objects.first()
        self.assertTrue(cita.cubierto_por_poliza)
        self.assertIsNotNone(cita.poliza)

    def test_crear_solicitud_poliza_agotada_muestra_warning(self):
        plan = PlanSalud.objects.create(nombre='Test', costo_mensual=Decimal('10'), consultas_maximas_anuales=1)
        poliza = Poliza.objects.create(
            paciente=self.paciente, plan=plan,
            fecha_inicio=date(2026, 1, 1), estado='Activo'
        )
        SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.odontologo,
            fecha_cita=date(2026, 5, 1), hora_cita=time(10, 0),
            cubierto_por_poliza=True, poliza=poliza, estado='Atendido'
        )
        self._login(grupo='Secretaria')
        response = self.client.post(reverse('crear_solicitud'), {
            'paciente': self.paciente.id,
            'especialista': self.odontologo.id,
            'fecha_cita': '2026-07-20',
            'hora_cita': '09:00',
        }, follow=True)
        self.assertContains(response, 'agotado')
        cita = SolicitudSecretaria.objects.last()
        self.assertFalse(cita.cubierto_por_poliza)


class PacienteCRUDTest(BaseTest):
    def test_registrar_paciente(self):
        self._login(grupo='Secretaria')
        response = self.client.post(reverse('registrar_paciente'), {
            'nombre': 'Maria', 'apellido': 'Gomez', 'cedula': '87654321',
            'codigo_telefono': '0414', 'numero_telefono': '7654321',
            'fecha_nacimiento': '1985-03-22',
            'status_afiliado': 'Afiliado', 'categoria_afiliado': 'Docente',
        }, follow=True)
        self.assertContains(response, 'exitosamente')
        self.assertTrue(Paciente.objects.filter(cedula='87654321').exists())


class LaboratorioFlowTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()

    def test_registrar_solicitud_lab(self):
        self._login(grupo='Laboratorio')
        response = self.client.post(reverse('registrar_laboratorio'), {
            'paciente': self.paciente.id,
            'prueba_laboratorio': 'Urianálisis',
            'fecha_solicitud': '2026-07-05'
        }, follow=True)
        self.assertContains(response, 'exitosamente')

    def test_procesar_solicitud_lab(self):
        solicitud = SolicitudLaboratorio.objects.create(
            paciente=self.paciente, prueba_laboratorio='Hemograma',
            fecha_solicitud=date(2026, 7, 5)
        )
        self._login(grupo='Laboratorio')
        response = self.client.post(reverse('solicitudes_pendientes_laboratorio'), {
            'solicitud_id': solicitud.id,
            'resultado': 'Valores normales',
            'costo': '30.00',
            'bioanalista': 'Dr. Hernandez'
        }, follow=True)
        self.assertContains(response, 'exitosamente')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'Procesado')
        self.assertEqual(solicitud.costo, Decimal('30.00'))


class TarifaMedicamentoCRUDTest(BaseTest):
    def test_crear_tarifa(self):
        self._login(grupo='Especialista')
        response = self.client.post(reverse('costos_especialista'), {
            'accion': 'crear',
            'especialidad': 'Dermatología',
            'costo_consulta': '60.00',
            'porcentaje_medico': '50.00',
        }, follow=True)
        self.assertContains(response, 'correctamente')
        self.assertTrue(TarifaEspecialidad.objects.filter(especialidad='Dermatología').exists())

    def test_crear_medicamento(self):
        self._login(grupo='Especialista')
        response = self.client.post(reverse('medicamentos_especialista'), {
            'accion': 'crear',
            'nombre': 'Ibuprofeno',
            'precio': '3.50',
            'cantidad_stock': 200,
        }, follow=True)
        self.assertContains(response, 'registrado')
        self.assertTrue(Medicamento.objects.filter(nombre='Ibuprofeno').exists())


class PolizaFlowTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente()
        self.plan = PlanSalud.objects.create(nombre='Plan Premium', costo_mensual=Decimal('50.00'))

    def test_crear_poliza(self):
        self._login(grupo='Administracion')
        response = self.client.post(reverse('poliza_crear'), {
            'paciente': self.paciente.id,
            'plan': self.plan.id,
            'fecha_inicio': '2026-01-01',
            'cuota_inicial': '10.00',
            'estado': 'Activo',
        }, follow=True)
        self.assertContains(response, 'creada')
        self.assertEqual(Poliza.objects.count(), 1)

    def test_registrar_gasto_descuenta_saldo(self):
        poliza = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1), saldo_restante=Decimal('500.00')
        )
        self._login(grupo='Administracion')
        response = self.client.post(reverse('poliza_registrar_gasto', args=[poliza.id]), {
            'concepto': 'Medicamentos',
            'monto': '100.00',
            'fecha': '2026-06-15',
        }, follow=True)
        self.assertContains(response, 'registrado')
        poliza.refresh_from_db()
        self.assertEqual(poliza.saldo_restante, Decimal('400.00'))

    def test_registrar_gasto_monto_invalido(self):
        poliza = Poliza.objects.create(
            paciente=self.paciente, plan=self.plan,
            fecha_inicio=date(2026, 1, 1), saldo_restante=Decimal('500.00')
        )
        self._login(grupo='Administracion')
        response = self.client.post(reverse('poliza_registrar_gasto', args=[poliza.id]), {
            'concepto': 'Test',
            'monto': 'no_numerico',
            'fecha': '2026-06-15',
        }, follow=True)
        self.assertContains(response, 'número')
        poliza.refresh_from_db()
        self.assertEqual(poliza.saldo_restante, Decimal('500.00'))


class AdminMenuTest(BaseTest):
    def test_menu_admin_agrega_rol_sin_borrar(self):
        user = self._crear_usuario('target', 'Test1234!', 'Medico')
        self._login(grupo='Administracion')
        response = self.client.post(reverse('menu_admin'), {
            'usuario_id': user.id,
            'rol_nombre': 'Odontologo'
        }, follow=True)
        self.assertContains(response, 'asignado')
        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name='Medico').exists())
        self.assertTrue(user.groups.filter(name='Odontologo').exists())

    def test_menu_admin_quita_todos_los_roles(self):
        user = self._crear_usuario('target', 'Test1234!', 'Medico')
        self._login(grupo='Administracion')
        response = self.client.post(reverse('menu_admin'), {
            'usuario_id': user.id,
            'rol_nombre': ''
        }, follow=True)
        self.assertContains(response, 'quitado')
        user.refresh_from_db()
        self.assertEqual(user.groups.count(), 0)

    def test_menu_admin_toggle_status(self):
        user = self._crear_usuario('target', 'Test1234!')
        self.assertTrue(user.is_active)
        self._login(grupo='Administracion')
        response = self.client.post(reverse('menu_admin'), {
            'usuario_id': user.id,
            'toggle_status': '1'
        }, follow=True)
        user.refresh_from_db()
        self.assertFalse(user.is_active)


class SaldosAdminTest(BaseTest):
    def test_saldos_filtro_respeta_conteo(self):
        self._crear_paciente(cedula='11111111', status_afiliado='Afiliado')
        self._crear_paciente(cedula='22222222', status_afiliado='Comunidad')
        self._crear_paciente(cedula='33333333', status_afiliado='Afiliado')
        self._login(grupo='Administracion')
        response = self.client.get(reverse('saldos_admin'), {'q': '33333333'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '33333333')
        self.assertNotContains(response, '11111111')


class ReporteAdminTest(BaseTest):
    def test_reporte_calcula_nomina(self):
        paciente = self._crear_paciente()
        medico = self._crear_usuario('dr', 'Test1234!', 'Medico')
        SolicitudSecretaria.objects.create(
            paciente=paciente, especialista=medico,
            fecha_cita=date(2026, 6, 1), hora_cita=time(10, 0),
            estado='Atendido', cobro_nomina=True
        )
        SolicitudSecretaria.objects.create(
            paciente=paciente, especialista=medico,
            fecha_cita=date(2026, 6, 2), hora_cita=time(11, 0),
            estado='Atendido', cobro_nomina=False
        )
        self._login(grupo='Administracion')
        response = self.client.get(reverse('reporte_admin'))
        self.assertContains(response, '50,00')
        self.assertContains(response, '2')


class LandingPageTest(BaseTest):
    def test_landing_muestra_botones_secretaria(self):
        self._login(grupo='Secretaria')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Secretaría')

    def test_landing_muestra_botones_medico(self):
        self._login(grupo='Medico')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Servicio Médico')

    def test_landing_muestra_botones_admin(self):
        self._login(grupo='Administracion')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Administración')


class ExportTest(BaseTest):
    def test_export_pacientes_csv_admin(self):
        self._crear_paciente()
        self._login(grupo='Administracion')
        response = self.client.get(reverse('exportar_pacientes_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('Juan', str(response.content))

    def test_export_pacientes_excel_admin(self):
        self._crear_paciente()
        self._login(grupo='Administracion')
        response = self.client.get(reverse('exportar_pacientes_excel'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])

    def test_export_report_excel_admin(self):
        self._login(grupo='Administracion')
        response = self.client.get(reverse('exportar_reporte_excel'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])

    def test_export_report_csv_admin(self):
        self._login(grupo='Administracion')
        response = self.client.get(reverse('exportar_reporte_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_export_denegado_sin_admin(self):
        self._login(grupo='Secretaria')
        response = self.client.get(reverse('exportar_pacientes_csv'))
        self.assertNotEqual(response.status_code, 200)


class PricingTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente_afiliado = self._crear_paciente(status_afiliado='Afiliado')
        self.paciente_comunidad = self._crear_paciente(cedula='87654321', status_afiliado='Comunidad')
        self.medico = self._crear_usuario('dr_medico', 'Test1234!', 'Medico')
        self.tarifa = TarifaEspecialidad.objects.create(
            especialidad='Medicina General', costo_consulta=Decimal('30.00'), activo=True
        )

    def _crear_cita(self, paciente, especialista=None, cubierto=False, estado='En Espera'):
        return SolicitudSecretaria.objects.create(
            paciente=paciente,
            especialista=especialista or self.medico,
            fecha_cita=date(2026, 7, 15),
            hora_cita=time(9, 0),
            motivo_consulta='Consulta de prueba',
            cubierto_por_poliza=cubierto,
            estado=estado,
        )

    def test_calcular_costo_cubierto_por_poliza(self):
        cita = self._crear_cita(paciente=self.paciente_afiliado, cubierto=True)
        costo, med, admin = cita.calcular_costo()
        self.assertEqual(costo, Decimal('0.00'))
        self.assertEqual(med, Decimal('0.00'))
        self.assertEqual(admin, Decimal('0.00'))

    def test_calcular_costo_particular_con_tarifa(self):
        cita = self._crear_cita(paciente=self.paciente_comunidad, cubierto=False)
        costo, med, admin = cita.calcular_costo()
        self.assertEqual(costo, Decimal('30.00'))
        self.assertEqual(med, Decimal('15.00'))
        self.assertEqual(admin, Decimal('15.00'))

    def test_calcular_costo_afiliado_sin_cobertura(self):
        cita = self._crear_cita(paciente=self.paciente_afiliado, cubierto=False)
        costo, med, admin = cita.calcular_costo()
        self.assertEqual(costo, Decimal('30.00'))

    def test_calcular_costo_sin_tarifa_retorna_cero(self):
        TarifaEspecialidad.objects.all().delete()
        cita = self._crear_cita(paciente=self.paciente_comunidad, cubierto=False)
        costo, med, admin = cita.calcular_costo()
        self.assertEqual(costo, Decimal('0.00'))

    def test_atender_cita_guarda_costo(self):
        user = self._login(grupo='Medico')
        cita = self._crear_cita(paciente=self.paciente_comunidad, especialista=user, estado='En Espera')
        url = reverse('atender_cita', args=[cita.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('citas_recibidas_medico'))
        cita.refresh_from_db()
        self.assertEqual(cita.estado, 'Atendido')
        self.assertEqual(cita.costo_consulta, Decimal('30.00'))
        self.assertEqual(cita.monto_medico, Decimal('15.00'))
        self.assertEqual(cita.monto_admin, Decimal('15.00'))

    def test_reporte_admin_muestra_totales(self):
        self._login(grupo='Administracion')
        cita = self._crear_cita(paciente=self.paciente_comunidad, especialista=self.medico, estado='Atendido')
        cita.costo_consulta = Decimal('30.00')
        cita.monto_medico = Decimal('15.00')
        cita.monto_admin = Decimal('15.00')
        cita.save()
        url = reverse('reporte_admin')
        response = self.client.get(url)
        self.assertContains(response, 'Total Ingresos')
        self.assertContains(response, '30')

    def test_calcular_costo_personalizado(self):
        self.tarifa.porcentaje_medico = Decimal('60.00')
        self.tarifa.save()
        cita = self._crear_cita(paciente=self.paciente_comunidad, cubierto=False)
        costo, med, admin = cita.calcular_costo()
        self.assertEqual(costo, Decimal('30.00'))
        self.assertEqual(med, Decimal('18.00'))
        self.assertEqual(admin, Decimal('12.00'))

    def test_calcular_costo_admin_cien_porciento(self):
        self.tarifa.porcentaje_medico = Decimal('0.00')
        self.tarifa.save()
        cita = self._crear_cita(paciente=self.paciente_comunidad, cubierto=False)
        costo, med, admin = cita.calcular_costo()
        self.assertEqual(costo, Decimal('30.00'))
        self.assertEqual(med, Decimal('0.00'))
        self.assertEqual(admin, Decimal('30.00'))

    def test_ingresos_especialistas_view(self):
        self._login(grupo='Administracion')
        cita = self._crear_cita(paciente=self.paciente_comunidad, especialista=self.medico, estado='Atendido')
        cita.costo_consulta = Decimal('30.00')
        cita.monto_medico = Decimal('15.00')
        cita.monto_admin = Decimal('15.00')
        cita.save()
        url = reverse('ingresos_especialistas')
        response = self.client.get(url)
        self.assertContains(response, 'dr_medico')
        self.assertContains(response, '30')


class AfiliadoCodigoTest(BaseTest):
    def test_codigo_auto_generado(self):
        p = self._crear_paciente(cedula='99999999')
        self.assertEqual(p.codigo_afiliado, 'IPP-99999999')

    def test_codigo_no_sobrescribe_existente(self):
        p = self._crear_paciente(cedula='88888888')
        codigo_original = p.codigo_afiliado
        p.nombre = 'Otro'
        p.save()
        self.assertEqual(p.codigo_afiliado, codigo_original)


class HistoriaClinicaPrintTest(BaseTest):
    def test_historia_clinica_print_200(self):
        p = self._crear_paciente()
        self._login(grupo='Medico')
        response = self.client.get(reverse('historia_clinica_print', args=[p.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Historia Clínica')
        self.assertContains(response, p.nombre)


class FacturaTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.paciente = self._crear_paciente(status_afiliado='Comunidad')
        self.medico = self._crear_usuario('dr_fact', 'Test1234!', 'Medico')
        self.tarifa = TarifaEspecialidad.objects.create(
            especialidad='Medicina General', costo_consulta=Decimal('30.00'), activo=True
        )
        self.cita = SolicitudSecretaria.objects.create(
            paciente=self.paciente, especialista=self.medico,
            fecha_cita=date(2026, 7, 20), hora_cita=time(10, 0),
            estado='Atendido', costo_consulta=Decimal('30.00'),
            monto_medico=Decimal('15.00'), monto_admin=Decimal('15.00'),
        )

    def test_factura_lista_admin(self):
        self._login(grupo='Administracion')
        response = self.client.get(reverse('facturas_lista'))
        self.assertEqual(response.status_code, 200)

    def test_factura_generar_y_detalle(self):
        self._login(grupo='Administracion')
        response = self.client.post(reverse('factura_generar', args=[self.cita.id]), {
            'iva': '16', 'descripcion': 'Consulta general'
        })
        factura = Factura.objects.get(cita=self.cita)
        self.assertRedirects(response, reverse('factura_detalle', args=[factura.id]))
        self.assertEqual(factura.subtotal, Decimal('30.00'))
        self.assertEqual(factura.iva, Decimal('4.80'))
        self.assertEqual(factura.total, Decimal('34.80'))
        self.assertEqual(factura.paciente_nombre, 'Juan Perez')
        response = self.client.get(reverse('factura_detalle', args=[factura.id]))
        self.assertContains(response, 'FAC-00001')
        self.assertContains(response, '34')

    def test_factura_duplicada_rechazada(self):
        Factura.objects.create(
            cita=self.cita, paciente_nombre='Test',
            paciente_cedula='11111111', subtotal=Decimal('0'),
            total=Decimal('0'),
        )
        self._login(grupo='Administracion')
        response = self.client.get(reverse('factura_generar', args=[self.cita.id]))
        self.assertRedirects(response, reverse('factura_detalle', args=[self.cita.factura.id]))


class ImportarPacientesTest(BaseTest):
    def test_importar_view_denegado_sin_admin(self):
        self._login(grupo='Secretaria')
        response = self.client.get(reverse('importar_pacientes_excel'))
        self.assertRedirects(response, reverse('home'))

    def test_importar_view_get_admin(self):
        self._login(grupo='Administracion')
        response = self.client.get(reverse('importar_pacientes_excel'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Importar Pacientes')


class EditarPacienteTest(BaseTest):
    def test_editar_paciente_get(self):
        self._login(grupo='Secretaria')
        p = self._crear_paciente()
        response = self.client.get(reverse('editar_paciente', args=[p.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, p.nombre)

    def test_editar_paciente_post(self):
        self._login(grupo='Secretaria')
        p = self._crear_paciente()
        response = self.client.post(reverse('editar_paciente', args=[p.id]), {
            'nombre': 'Pedro', 'apellido': 'Gomez', 'cedula': p.cedula,
            'codigo_telefono': '0412', 'numero_telefono': '1234567',
            'fecha_nacimiento': '1990-05-15',
            'status_afiliado': 'Afiliado', 'categoria_afiliado': 'Jubilado',
        })
        p.refresh_from_db()
        self.assertEqual(p.nombre, 'Pedro')
        self.assertEqual(p.apellido, 'Gomez')

    def test_eliminar_paciente(self):
        self._login(grupo='Secretaria')
        p = self._crear_paciente()
        response = self.client.post(reverse('eliminar_paciente', args=[p.id]))
        p.refresh_from_db()
        self.assertFalse(p.activo)
        self.assertRedirects(response, reverse('registrar_paciente'))


class RecetaTest(BaseTest):
    def test_receta_crear(self):
        user = self._login(grupo='Medico')
        p = self._crear_paciente()
        cita = SolicitudSecretaria.objects.create(paciente=p, especialista=user, fecha_cita=date.today(), hora_cita=time(10,0), estado='Atendido')
        med = Medicamento.objects.create(nombre='Paracetamol', precio=10, cantidad_stock=100)
        response = self.client.post(reverse('receta_crear', args=[cita.id]), {
            'medicamento': med.id, 'cantidad': 1, 'dosis': '1 cada 8h', 'duracion': '7 días',
        })
        self.assertEqual(cita.recetas.count(), 1)
        receta = cita.recetas.first()
        self.assertEqual(receta.medicamento, med)
        self.assertEqual(receta.dosis, '1 cada 8h')

    def test_receta_crear_denegado(self):
        user = self._login(grupo='Secretaria')
        p = self._crear_paciente()
        cita = SolicitudSecretaria.objects.create(paciente=p, especialista=user, fecha_cita=date.today(), hora_cita=time(10,0), estado='Atendido')
        response = self.client.get(reverse('receta_crear', args=[cita.id]))
        self.assertRedirects(response, reverse('home'))


class FacturaPagoTest(BaseTest):
    def test_marcar_pagada_get(self):
        self._login(grupo='Administracion')
        p = self._crear_paciente()
        cita = SolicitudSecretaria.objects.create(paciente=p, fecha_cita=date.today(), hora_cita=time(10,0), estado='Atendido')
        factura = Factura.objects.create(cita=cita, subtotal=100, total=100, paciente_nombre='Test')
        response = self.client.get(reverse('marcar_factura_pagada', args=[factura.id]))
        self.assertEqual(response.status_code, 200)

    def test_marcar_pagada_post(self):
        self._login(grupo='Administracion')
        p = self._crear_paciente()
        cita = SolicitudSecretaria.objects.create(paciente=p, fecha_cita=date.today(), hora_cita=time(10,0), estado='Atendido')
        factura = Factura.objects.create(cita=cita, subtotal=100, total=100, paciente_nombre='Test')
        response = self.client.post(reverse('marcar_factura_pagada', args=[factura.id]), {'metodo_pago': 'Efectivo'})
        factura.refresh_from_db()
        self.assertTrue(factura.pagada)
        self.assertEqual(factura.metodo_pago, 'Efectivo')
        self.assertIsNotNone(factura.fecha_pago)

    def test_reporte_caja(self):
        self._login(grupo='Administracion')
        response = self.client.get(reverse('reporte_caja'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reporte de Caja')

    def test_recibo_factura(self):
        self._login(grupo='Administracion')
        p = self._crear_paciente()
        cita = SolicitudSecretaria.objects.create(paciente=p, fecha_cita=date.today(), hora_cita=time(10,0), estado='Atendido')
        factura = Factura.objects.create(cita=cita, subtotal=100, total=100, paciente_nombre='Test', pagada=True, metodo_pago='Efectivo', fecha_pago=now())
        response = self.client.get(reverse('recibo_factura', args=[factura.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'RECIBO')


# class PortalPacienteTest(BaseTest):
#     def test_portal_registro_get(self):
#         response = self.client.get(reverse('portal_registro'))
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, 'Registro al Portal')
# 
#     def test_portal_registro_post(self):
#         p = self._crear_paciente(cedula='12345679')
#         response = self.client.post(reverse('portal_registro'), {
#             'cedula': '12345679', 'codigo_afiliado': '',
#             'password': 'MiPass123!', 'password2': 'MiPass123!',
#         })
#         p.refresh_from_db()
#         self.assertIsNotNone(p.usuario)
#         self.assertTrue(User.objects.filter(username='PAC-V12345679').exists())
#         self.assertRedirects(response, reverse('portal_login'))
# 
#     def test_portal_login_get(self):
#         response = self.client.get(reverse('portal_login'))
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, 'Portal del Paciente')
# 
#     def test_portal_inicio_authenticated(self):
#         p = self._crear_paciente(cedula='99999999')
#         user = User.objects.create_user(username='PAC-V99999999', password='Test1234!')
#         p.usuario = user
#         p.save()
#         self.client.force_login(user)
#         response = self.client.get(reverse('portal_inicio'))
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, p.nombre)
