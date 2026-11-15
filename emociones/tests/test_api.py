"""Pruebas de la página de cámara y de la API /api/analizar/."""
import cv2
import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse


def jpeg_de_prueba(ancho=320, alto=240):
    """Genera un JPEG sintético en memoria."""
    imagen = np.full((alto, ancho, 3), 127, dtype=np.uint8)
    ok, buffer = cv2.imencode('.jpg', imagen)
    assert ok
    return SimpleUploadedFile('frame.jpg', buffer.tobytes(), content_type='image/jpeg')


class PaginaCamaraTests(TestCase):
    def test_pagina_carga(self):
        resp = self.client.get(reverse('emociones:camara'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="video"')


class ApiAnalizarTests(TestCase):
    url = reverse('emociones:analizar')

    def test_get_no_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_sin_frame_devuelve_400(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])

    def test_imagen_invalida_devuelve_400(self):
        basura = SimpleUploadedFile('frame.jpg', b'no es una imagen', content_type='image/jpeg')
        resp = self.client.post(self.url, {'frame': basura})
        self.assertEqual(resp.status_code, 400)

    def test_frame_valido(self):
        resp = self.client.post(self.url, {'frame': jpeg_de_prueba(320, 240)})
        self.assertEqual(resp.status_code, 200)
        datos = resp.json()
        self.assertTrue(datos['ok'])
        self.assertEqual((datos['ancho'], datos['alto']), (320, 240))
        self.assertIsInstance(datos['rostros'], list)
        self.assertIn('ms', datos)


class ApiAnalizarConRostroTests(TestCase):
    def test_detecta_rostro_y_emocion(self):
        from pathlib import Path
        ruta = Path(__file__).parent / 'imagenes' / 'con_rostro.jpg'
        frame = SimpleUploadedFile('frame.jpg', ruta.read_bytes(), content_type='image/jpeg')
        resp = self.client.post(reverse('emociones:analizar'), {'frame': frame, 'cliente': 'abc123'})
        self.assertEqual(resp.status_code, 200)
        rostros = resp.json()['rostros']
        self.assertGreaterEqual(len(rostros), 1)
        for clave in ('id', 'caja', 'emocion', 'confianza', 'probabilidades'):
            self.assertIn(clave, rostros[0])
