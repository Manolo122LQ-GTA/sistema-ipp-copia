from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse

class DebugLoginTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='debuguser',
            password='Abc123!@#$%xyz78'
        )
        Group.objects.create(name='Secretaria')
    
    def test_debug_login_flow(self):
        # Paso 1: POST a login
        response = self.client.post(reverse('login'), {
            'username': 'debuguser',
            'password': 'Abc123!@#$%xyz78'
        })
        print(f"Login response status: {response.status_code}")
        print(f"Login response URL: {response.url if hasattr(response, 'url') else 'N/A'}")
        print(f"Login response location: {response.get('Location', 'N/A')}")
        
        # Paso 2: Verificar si el usuario está autenticado en la sesión
        print(f"User authenticated after login: {self.client.session.get('_auth_user_id', 'N/A')}")
        
        # Paso 3: Hacer GET a home directamente
        response2 = self.client.get(reverse('home'))
        print(f"Home response status: {response2.status_code}")
        print(f"Home response URL: {response2.url if hasattr(response2, 'url') else 'N/A'}")
