"""Pruebas del módulo de visión (detector, clasificador, seguimiento, pipeline)."""
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from django.test import SimpleTestCase

from emociones.servicios import obtener_analizador
from emociones.vision import EMOCIONES, SeguidorRostros, decodificar_jpeg
from emociones.vision.seguimiento import iou

IMAGEN_ROSTRO = Path(__file__).parent / 'imagenes' / 'con_rostro.jpg'


class DetectorYClasificadorTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analizador = obtener_analizador()
        cls.imagen = cv2.imread(str(IMAGEN_ROSTRO))

    def test_modelos_existen(self):
        self.assertTrue(settings.MODELO_ROSTROS.exists())
        self.assertTrue(settings.MODELO_EMOCIONES.exists())

    def test_detecta_rostro_en_imagen(self):
        rostros = self.analizador.detector.detectar(self.imagen)
        self.assertGreaterEqual(len(rostros), 1)
        alto, ancho = self.imagen.shape[:2]
        for r in rostros:
            self.assertGreaterEqual(r.x, 0)
            self.assertGreaterEqual(r.y, 0)
            self.assertLessEqual(r.x + r.ancho, ancho)
            self.assertLessEqual(r.y + r.alto, alto)

    def test_sin_rostro_en_imagen_vacia(self):
        vacia = np.zeros((240, 320, 3), dtype=np.uint8)
        self.assertEqual(self.analizador.detector.detectar(vacia), [])

    def test_clasificador_devuelve_probabilidades(self):
        probs = self.analizador.clasificador.clasificar(self.imagen[90:140, 220:260])
        self.assertEqual(list(probs), EMOCIONES)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=4)
        self.assertTrue(all(0 <= p <= 1 for p in probs.values()))

    def test_clasificar_lote_vacio(self):
        self.assertEqual(self.analizador.clasificador.clasificar_lote([]).shape, (0, 8))

    def test_pipeline_completo(self):
        resultados = self.analizador.analizar(self.imagen, cliente='prueba')
        self.assertGreaterEqual(len(resultados), 1)
        r = resultados[0]
        self.assertIn(r['emocion'], EMOCIONES)
        self.assertEqual(set(r['probabilidades']), set(EMOCIONES))
        self.assertEqual(len(r['caja']), 4)

    def test_decodificar_jpeg_invalido(self):
        self.assertIsNone(decodificar_jpeg(b''))
        self.assertIsNone(decodificar_jpeg(b'no es imagen'))


class SeguimientoTests(SimpleTestCase):
    def test_iou(self):
        self.assertEqual(iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)
        self.assertEqual(iou([0, 0, 10, 10], [20, 20, 5, 5]), 0.0)

    def test_mantiene_id_y_suaviza(self):
        seguidor = SeguidorRostros(alfa=0.5)
        p1 = np.eye(8)[0]  # 100% neutral
        p2 = np.eye(8)[1]  # 100% felicidad
        id1 = seguidor.actualizar([[10, 10, 50, 50]], np.array([p1]))[0].id
        pista = seguidor.actualizar([[12, 11, 50, 50]], np.array([p2]))[0]
        self.assertEqual(pista.id, id1)                 # mismo rostro, mismo id
        self.assertAlmostEqual(pista.probs[0], 0.5)     # promedio suavizado
        self.assertAlmostEqual(pista.probs[1], 0.5)

    def test_rostro_lejano_es_nuevo(self):
        seguidor = SeguidorRostros()
        p = np.array([np.eye(8)[0]])
        a = seguidor.actualizar([[0, 0, 40, 40]], p)[0].id
        b = seguidor.actualizar([[300, 300, 40, 40]], p)[0].id
        self.assertNotEqual(a, b)

    def test_descarta_pistas_perdidas(self):
        seguidor = SeguidorRostros(max_frames_perdido=2)
        seguidor.actualizar([[0, 0, 40, 40]], np.array([np.eye(8)[0]]))
        for _ in range(3):
            seguidor.actualizar([], np.empty((0, 8)))
        self.assertEqual(seguidor.pistas, [])
