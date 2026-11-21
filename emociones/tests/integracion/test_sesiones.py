"""Pruebas de integración de las sesiones: crear, analizar con guardado y finalizar."""
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from emociones import registro
from emociones.models import RegistroEmocion, SesionAnalisis
from emociones.tests.utilidades import frame_con_rostro


class SesionesApiTests(TestCase):
    def setUp(self):
        registro._ultimo_guardado.clear()

    def iniciar(self, nombre='Prueba'):
        resp = self.client.post(reverse('emociones:iniciar_sesion'), {'nombre': nombre})
        self.assertEqual(resp.status_code, 200)
        return resp.json()['sesion']

    def test_iniciar_crea_sesion(self):
        """Iniciar una sesión la crea en la base de datos como «en curso»."""
        pk = self.iniciar('Clase de Construcción')
        sesion = SesionAnalisis.objects.get(pk=pk)
        self.assertEqual(sesion.nombre, 'Clase de Construcción')
        self.assertTrue(sesion.en_curso)

    def test_nombre_vacio_usa_valor_por_defecto(self):
        """Una sesión sin nombre recibe «Sesión sin nombre»."""
        pk = self.iniciar('   ')
        self.assertEqual(SesionAnalisis.objects.get(pk=pk).nombre, 'Sesión sin nombre')

    def test_finalizar_marca_fin(self):
        """Finalizar una sesión registra su hora de fin."""
        pk = self.iniciar()
        resp = self.client.post(reverse('emociones:finalizar_sesion', args=[pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SesionAnalisis.objects.get(pk=pk).en_curso)

    def test_finalizar_inexistente_404(self):
        """Finalizar una sesión inexistente responde 404."""
        resp = self.client.post(reverse('emociones:finalizar_sesion', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_analizar_guarda_registros_con_limite_por_segundo(self):
        """Durante una sesión se guarda como máximo una muestra por segundo."""
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
        """No se guardan registros en una sesión ya finalizada."""
        pk = self.iniciar()
        self.client.post(reverse('emociones:finalizar_sesion', args=[pk]))
        resp = self.client.post(reverse('emociones:analizar'), {'frame': frame_con_rostro(), 'sesion': pk})
        self.assertEqual(resp.json()['guardados'], 0)
        self.assertEqual(RegistroEmocion.objects.count(), 0)
