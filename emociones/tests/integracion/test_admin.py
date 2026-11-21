"""Pruebas de integración del panel de administración de Django."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from emociones.models import RegistroEmocion, SesionAnalisis


class AdminTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.com', 'clave'))
        sesion = SesionAnalisis.objects.create(nombre='Sesión admin')
        RegistroEmocion.objects.create(sesion=sesion, rostro_id=1, emocion='sorpresa',
                                       confianza=0.7, probabilidades={'sorpresa': 0.7})
        self.sesion = sesion

    def test_listados_y_detalle_cargan(self):
        """El panel de administración muestra sesiones y registros."""
        for url in [
            reverse('admin:emociones_sesionanalisis_changelist'),
            reverse('admin:emociones_sesionanalisis_change', args=[self.sesion.pk]),
            reverse('admin:emociones_registroemocion_changelist'),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
        resp = self.client.get(reverse('admin:emociones_sesionanalisis_changelist'))
        self.assertContains(resp, 'Sesión admin')
        self.assertContains(resp, 'sorpresa')
