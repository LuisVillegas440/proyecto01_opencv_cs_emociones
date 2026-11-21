"""Pruebas de integración de la API /api/analizar/: HTTP -> vista -> OpenCV -> JSON."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from emociones.tests.utilidades import frame_con_rostro, jpeg_de_prueba


class ApiAnalizarTests(TestCase):
    url = reverse('emociones:analizar')

    def test_get_no_permitido(self):
        """La API de análisis rechaza peticiones GET (405)."""
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_sin_frame_devuelve_400(self):
        """La API de análisis responde 400 si no se envía imagen."""
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])

    def test_imagen_invalida_devuelve_400(self):
        """La API de análisis responde 400 si el archivo no es una imagen."""
        basura = SimpleUploadedFile('frame.jpg', b'no es una imagen', content_type='image/jpeg')
        resp = self.client.post(self.url, {'frame': basura})
        self.assertEqual(resp.status_code, 400)

    def test_frame_valido(self):
        """La API procesa un frame válido y devuelve tamaño, rostros y tiempo de proceso."""
        resp = self.client.post(self.url, {'frame': jpeg_de_prueba(320, 240)})
        self.assertEqual(resp.status_code, 200)
        datos = resp.json()
        self.assertTrue(datos['ok'])
        self.assertEqual((datos['ancho'], datos['alto']), (320, 240))
        self.assertIsInstance(datos['rostros'], list)
        self.assertIn('ms', datos)


class ApiAnalizarConRostroTests(TestCase):
    def test_detecta_rostro_y_emocion(self):
        """La API detecta un rostro real y devuelve su emoción y probabilidades."""
        resp = self.client.post(reverse('emociones:analizar'),
                                {'frame': frame_con_rostro(), 'cliente': 'abc123'})
        self.assertEqual(resp.status_code, 200)
        rostros = resp.json()['rostros']
        self.assertGreaterEqual(len(rostros), 1)
        for clave in ('id', 'caja', 'emocion', 'confianza', 'probabilidades'):
            self.assertIn(clave, rostros[0])
