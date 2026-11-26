import json
import re
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from pacientes.admin import LogActividadAdmin
from pacientes.models import LogActividad, PerfilUsuario


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class SeguridadEvaluacionTest(TestCase):
    """Pruebas de las mejoras de seguridad del Instrumento de Evaluación Trayecto III."""

    def setUp(self):
        self.grupo_admin, _ = Group.objects.get_or_create(name='Administracion')
        self.grupo_med, _ = Group.objects.get_or_create(name='Medico')

        self.admin = User.objects.create_user(
            username='admin_eval',
            password='PasswordSegura!2026#1234',
            email='admin@ipp.local',
        )
        self.admin.groups.add(self.grupo_admin)
        PerfilUsuario.objects.create(usuario=self.admin, aprobado=True)

        self.medico = User.objects.create_user(
            username='medico_eval',
            password='PasswordSegura!2026#1234',
            email='medico@ipp.local',
        )
        self.medico.groups.add(self.grupo_med)
        self.perfil_medico = PerfilUsuario.objects.create(
            usuario=self.medico,
            aprobado=True,
        )

    def test_bitacora_inmutable(self):
        log = LogActividad.objects.create(
            usuario=self.admin,
            accion='Acción inicial',
            modelo='User',
            objeto_id=self.admin.id,
        )
        log.accion = 'Acción alterada'
        with self.assertRaises(ValidationError):
            log.save()
        with self.assertRaises(PermissionDenied):
            log.delete()

        admin_view = LogActividadAdmin(LogActividad, AdminSite())
        self.assertFalse(admin_view.has_add_permission(None))
        self.assertFalse(admin_view.has_change_permission(None, log))
        self.assertFalse(admin_view.has_delete_permission(None, log))

    def test_eliminar_usuario_deniega_con_403_a_no_admin(self):
        self.client.force_login(self.medico)
        respuesta = self.client.get(reverse('admin_eliminar_usuario', args=[self.admin.id]))
        self.assertEqual(respuesta.status_code, 403)

    def test_eliminar_usuario_exige_password_correcta(self):
        self.client.force_login(self.admin)
        url = reverse('admin_eliminar_usuario', args=[self.medico.id])

        resp_mal = self.client.post(url, {'password_admin': 'clave-incorrecta'})
        self.assertEqual(resp_mal.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.medico.id).exists())

        resp_ok = self.client.post(url, {'password_admin': 'PasswordSegura!2026#1234'})
        self.assertRedirects(resp_ok, reverse('menu_admin'))
        self.assertFalse(User.objects.filter(pk=self.medico.id).exists())
        self.assertTrue(
            LogActividad.objects.filter(accion__icontains='Eliminó al usuario medico_eval').exists()
        )

    def test_respaldo_bd_403_y_descarga_json(self):
        self.client.force_login(self.medico)
        resp_forbidden = self.client.get(reverse('respaldo_bd'))
        self.assertEqual(resp_forbidden.status_code, 403)

        self.client.force_login(self.admin)
        resp_mal = self.client.post(
            reverse('respaldo_bd'),
            {'password_admin': 'incorrecta', 'accion': 'descargar'},
        )
        self.assertEqual(resp_mal.status_code, 200)

        resp_ok = self.client.post(
            reverse('respaldo_bd'),
            {'password_admin': 'PasswordSegura!2026#1234', 'accion': 'descargar'},
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.assertEqual(resp_ok['Content-Type'], 'application/json; charset=utf-8')
        datos = json.loads(resp_ok.content.decode('utf-8'))
        self.assertIsInstance(datos, list)
        self.assertTrue(
            LogActividad.objects.filter(accion__icontains='Generó respaldo de base de datos').exists()
        )
        # Limpiar archivo temporal creado en respaldos/ durante el test
        import os
        from django.conf import settings
        disp = resp_ok.get('Content-Disposition', '')
        match_archivo = re.search(r'filename="([^"]+)"', disp)
        if match_archivo:
            ruta_test = settings.BASE_DIR / 'respaldos' / match_archivo.group(1)
            if os.path.exists(ruta_test):
                os.remove(ruta_test)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_login_2fa_envia_otp_y_autentica(self):
        self.perfil_medico.autenticacion_2fa = True
        self.perfil_medico.save(update_fields=['autenticacion_2fa'])

        resp_login = self.client.post(reverse('login'), {
            'username': 'medico_eval',
            'password': 'PasswordSegura!2026#1234',
        })
        self.assertRedirects(resp_login, reverse('verificar_2fa_login'))
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r'(\d{6})', mail.outbox[0].body)
        self.assertIsNotNone(match)
        codigo = match.group(1)

        # Código incorrecto no inicia sesión
        resp_mal = self.client.post(reverse('verificar_2fa_login'), {'codigo': '000000'})
        self.assertEqual(resp_mal.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

        # Código correcto completa el login
        resp_ok = self.client.post(reverse('verificar_2fa_login'), {'codigo': codigo})
        self.assertRedirects(resp_ok, reverse('home'))
        self.assertEqual(str(self.medico.id), str(self.client.session.get('_auth_user_id')))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_login_2fa_recuerda_dispositivo_confiable(self):
        # 2FA viene activo por defecto
        self.assertTrue(self.perfil_medico.autenticacion_2fa)

        # Primer inicio de sesión en este navegador pide código 2FA
        resp_login = self.client.post(reverse('login'), {
            'username': 'medico_eval',
            'password': 'PasswordSegura!2026#1234',
        })
        self.assertRedirects(resp_login, reverse('verificar_2fa_login'))
        codigo = re.search(r'(\d{6})', mail.outbox[0].body).group(1)
        resp_ok = self.client.post(reverse('verificar_2fa_login'), {'codigo': codigo})
        self.assertRedirects(resp_ok, reverse('home'))
        self.assertIn('ipp_2fa_device', self.client.cookies)

        # Cerrar sesión y volver a entrar en el mismo navegador: no vuelve a pedir código
        self.client.post(reverse('logout'))
        mail.outbox.clear()
        resp_relogin = self.client.post(reverse('login'), {
            'username': 'medico_eval',
            'password': 'PasswordSegura!2026#1234',
        })
        self.assertRedirects(resp_relogin, reverse('home'))
        self.assertEqual(len(mail.outbox), 0)

        # En otro navegador (sin cookie de dispositivo), sí pide código 2FA
        self.client.post(reverse('logout'))
        otro_navegador = Client()
        resp_otro = otro_navegador.post(reverse('login'), {
            'username': 'medico_eval',
            'password': 'PasswordSegura!2026#1234',
        })
        self.assertRedirects(resp_otro, reverse('verificar_2fa_login'))

        # El superusuario (admin) queda exento de 2FA al iniciar sesión
        superadmin = User.objects.create_superuser(
            username='admin',
            password='PasswordSegura!2026#1234',
            email='admin_super@ipp.local',
        )
        PerfilUsuario.objects.create(usuario=superadmin, aprobado=True)
        resp_admin = otro_navegador.post(reverse('login'), {
            'username': 'admin',
            'password': 'PasswordSegura!2026#1234',
        })
        self.assertRedirects(resp_admin, reverse('home'))

    def test_perfil_toggle_2fa_requiere_password(self):
        self.client.force_login(self.medico)
        resp_mal = self.client.post(reverse('perfil_usuario'), {
            'accion': 'toggle_2fa',
            'password_admin': 'mala',
        })
        self.assertEqual(resp_mal.status_code, 200)
        self.perfil_medico.refresh_from_db()
        self.assertTrue(self.perfil_medico.autenticacion_2fa)

        resp_ok = self.client.post(reverse('perfil_usuario'), {
            'accion': 'toggle_2fa',
            'password_admin': 'PasswordSegura!2026#1234',
        })
        self.assertRedirects(resp_ok, reverse('perfil_usuario'))
        self.perfil_medico.refresh_from_db()
        self.assertFalse(self.perfil_medico.autenticacion_2fa)

    def test_autodesbloqueo_restringido_al_administrador(self):
        resp_login = self.client.get(reverse('login'))
        self.assertEqual(resp_login.status_code, 200)
        self.assertNotContains(resp_login, reverse('desbloqueo_solicitar'))
        self.assertNotContains(resp_login, reverse('desbloqueo_preguntas_solicitar'))

        self.assertEqual(self.client.get(reverse('desbloqueo_solicitar')).status_code, 403)
        self.assertEqual(self.client.get(reverse('desbloqueo_verificar')).status_code, 403)
        self.assertEqual(self.client.get(reverse('desbloqueo_preguntas_solicitar')).status_code, 403)
        self.assertEqual(self.client.get(reverse('desbloqueo_preguntas_verificar')).status_code, 403)

    def test_bitacora_filtros_paginacion_csv_y_permisos(self):
        # Usuario no administrador recibe 403
        self.client.force_login(self.medico)
        self.assertEqual(self.client.get(reverse('ver_logs')).status_code, 403)

        # Crear registros variados (más de 30 para probar paginación)
        from django.utils.timezone import localdate
        LogActividad.objects.create(
            usuario=self.admin,
            accion='Inicio de sesión exitoso',
            modelo='User',
            objeto_id=self.admin.id,
            ip_address='127.0.0.1',
            detalle='Autenticación estándar',
        )
        LogActividad.objects.create(
            usuario=self.medico,
            accion='Intento de inicio de sesión fallido',
            modelo='User',
            objeto_id=self.medico.id,
            ip_address='10.0.0.5',
            detalle='Contraseña incorrecta',
        )
        for i in range(32):
            LogActividad.objects.create(
                usuario=self.admin,
                accion=f'Acción de prueba {i}',
                modelo='Paciente',
                objeto_id=i + 1,
                ip_address='127.0.0.1',
            )

        self.client.force_login(self.admin)
        hoy_str = localdate().isoformat()

        # Vista principal: KPIs > 0, estilos legibles y paginación
        resp = self.client.get(reverse('ver_logs'))
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.context['registros_hoy'], 0)
        self.assertGreater(resp.context['eventos_seguridad_hoy'], 0)
        self.assertGreater(resp.context['usuarios_activos_hoy'], 0)
        self.assertTrue(resp.context['page_obj'].has_next())
        self.assertContains(resp, '127.0.0.1')

        # Página 2
        resp_p2 = self.client.get(reverse('ver_logs'), {'page': 2})
        self.assertEqual(resp_p2.status_code, 200)
        self.assertContains(resp_p2, '#fde8e8')
        self.assertContains(resp_p2, '#def7ec')

        # Filtros por texto, usuario, módulo y rango de fechas
        resp_filtro = self.client.get(reverse('ver_logs'), {
            'q': '10.0.0.5',
            'usuario': self.medico.id,
            'modelo': 'User',
            'fecha_desde': hoy_str,
            'fecha_hasta': hoy_str,
        })
        self.assertEqual(resp_filtro.status_code, 200)
        self.assertEqual(resp_filtro.context['total_filtrados'], 1)
        self.assertContains(resp_filtro, 'Intento de inicio de sesión fallido')

        # Exportación CSV respetando filtros
        resp_csv = self.client.get(reverse('ver_logs'), {
            'q': '10.0.0.5',
            'exportar': 'csv',
        })
        self.assertEqual(resp_csv.status_code, 200)
        self.assertIn('text/csv', resp_csv['Content-Type'])
        contenido_csv = resp_csv.content.decode('utf-8-sig')
        self.assertIn('Intento de inicio de sesión fallido', contenido_csv)
        self.assertNotIn('Acción de prueba 0', contenido_csv)
