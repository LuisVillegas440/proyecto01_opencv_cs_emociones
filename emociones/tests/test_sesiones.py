"""Pruebas de sesiones de análisis, guardado de registros y panel de admin."""
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from emociones import registro
from emociones.models import RegistroEmocion, SesionAnalisis

IMAGEN_ROSTRO = Path(__file__).parent / 'imagenes' / 'con_rostro.jpg'


def frame_con_rostro():
    return SimpleUploadedFile('frame.jpg', IMAGEN_ROSTRO.read_bytes(), content_type='image/jpeg')


class SesionesApiTests(TestCase):
    def setUp(self):
        registro._ultimo_guardado.clear()

    def iniciar(self, nombre='Prueba'):
        resp = self.client.post(reverse('emociones:iniciar_sesion'), {'nombre': nombre})
        self.assertEqual(resp.status_code, 200)
        return resp.json()['sesion']

    def test_iniciar_crea_sesion(self):
        pk = self.iniciar('Clase de Construcción')
        sesion = SesionAnalisis.objects.get(pk=pk)
        self.assertEqual(sesion.nombre, 'Clase de Construcción')
        self.assertTrue(sesion.en_curso)

    def test_nombre_vacio_usa_valor_por_defecto(self):
        pk = self.iniciar('   ')
        self.assertEqual(SesionAnalisis.objects.get(pk=pk).nombre, 'Sesión sin nombre')

    def test_finalizar_marca_fin(self):
        pk = self.iniciar()
        resp = self.client.post(reverse('emociones:finalizar_sesion', args=[pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SesionAnalisis.objects.get(pk=pk).en_curso)

    def test_finalizar_inexistente_404(self):
        resp = self.client.post(reverse('emociones:finalizar_sesion', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_analizar_guarda_registros_con_limite_por_segundo(self):
        pk = self.iniciar()
        url = reverse('emociones:analizar')
        r1 = self.client.post(url, {'frame': frame_con_rostro(), 'sesion': pk, 'cliente': 'c1'}).json()
        r2 = self.client.post(url, {'frame': frame_con_rostro(), 'sesion': pk, 'cliente': 'c1'}).json()
        self.assertGreaterEqual(r1['guardados'], 1)
        self.assertEqual(r2['guardados'], 0)  # mismo segundo: no se guarda de nuevo
        registro_db = RegistroEmocion.objects.get(sesion_id=pk)
        self.assertEqual(set(registro_db.probabilidades), set(r1['rostros'][0]['probabilidades']))

        # Simular que pasó más de un segundo.
        with mock.patch('emociones.registro.time.monotonic', return_value=10**9):
            r3 = self.client.post(url, {'frame': frame_con_rostro(), 'sesion': pk}).json()
        self.assertGreaterEqual(r3['guardados'], 1)

    def test_no_guarda_en_sesion_finalizada(self):
        pk = self.iniciar()
        self.client.post(reverse('emociones:finalizar_sesion', args=[pk]))
        resp = self.client.post(reverse('emociones:analizar'), {'frame': frame_con_rostro(), 'sesion': pk})
        self.assertEqual(resp.json()['guardados'], 0)
        self.assertEqual(RegistroEmocion.objects.count(), 0)

    def test_emocion_predominante(self):
        sesion = SesionAnalisis.objects.create(nombre='x')
        for emocion in ['felicidad', 'felicidad', 'neutral']:
            RegistroEmocion.objects.create(sesion=sesion, rostro_id=1, emocion=emocion,
                                           confianza=0.9, probabilidades={})
        self.assertEqual(sesion.emocion_predominante(), 'felicidad')
        self.assertIsNone(SesionAnalisis.objects.create(nombre='y').emocion_predominante())


class AdminTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.com', 'clave'))
        sesion = SesionAnalisis.objects.create(nombre='Sesión admin')
        RegistroEmocion.objects.create(sesion=sesion, rostro_id=1, emocion='sorpresa',
                                       confianza=0.7, probabilidades={'sorpresa': 0.7})
        self.sesion = sesion

    def test_listados_y_detalle_cargan(self):
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
