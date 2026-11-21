"""Pruebas unitarias del módulo de visión con OpenCV: detector, clasificador y pipeline."""
import cv2
import numpy as np
from django.conf import settings
from django.test import SimpleTestCase

from emociones.servicios import obtener_analizador
from emociones.tests.utilidades import IMAGEN_ROSTRO
from emociones.vision import EMOCIONES, decodificar_jpeg


class DetectorYClasificadorTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analizador = obtener_analizador()
        cls.imagen = cv2.imread(str(IMAGEN_ROSTRO))

    def test_modelos_existen(self):
        """Los archivos de los modelos YuNet y FER+ existen en modelos_ml/."""
        self.assertTrue(settings.MODELO_ROSTROS.exists())
        self.assertTrue(settings.MODELO_EMOCIONES.exists())

    def test_detecta_rostro_en_imagen(self):
        """YuNet detecta al menos un rostro en una foto real y la caja queda dentro de la imagen."""
        rostros = self.analizador.detector.detectar(self.imagen)
        self.assertGreaterEqual(len(rostros), 1)
        alto, ancho = self.imagen.shape[:2]
        for r in rostros:
            self.assertGreaterEqual(r.x, 0)
            self.assertGreaterEqual(r.y, 0)
            self.assertLessEqual(r.x + r.ancho, ancho)
            self.assertLessEqual(r.y + r.alto, alto)

    def test_sin_rostro_en_imagen_vacia(self):
        """En una imagen vacía no se detecta ningún rostro."""
        vacia = np.zeros((240, 320, 3), dtype=np.uint8)
        self.assertEqual(self.analizador.detector.detectar(vacia), [])

    def test_clasificador_devuelve_probabilidades(self):
        """FER+ devuelve las 8 emociones con probabilidades entre 0 y 1 que suman 1."""
        probs = self.analizador.clasificador.clasificar(self.imagen[90:140, 220:260])
        self.assertEqual(list(probs), EMOCIONES)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=4)
        self.assertTrue(all(0 <= p <= 1 for p in probs.values()))

    def test_clasificar_lote_vacio(self):
        """Clasificar una lista vacía de rostros devuelve una matriz vacía sin fallar."""
        self.assertEqual(self.analizador.clasificador.clasificar_lote([]).shape, (0, 8))

    def test_pipeline_completo(self):
        """El pipeline completo (detección + reconocimiento) devuelve emoción, caja y probabilidades."""
        resultados = self.analizador.analizar(self.imagen, cliente='prueba')
        self.assertGreaterEqual(len(resultados), 1)
        r = resultados[0]
        self.assertIn(r['emocion'], EMOCIONES)
        self.assertEqual(set(r['probabilidades']), set(EMOCIONES))
        self.assertEqual(len(r['caja']), 4)

    def test_decodificar_jpeg_invalido(self):
        """Datos vacíos o que no son imagen se rechazan sin lanzar errores."""
        self.assertIsNone(decodificar_jpeg(b''))
        self.assertIsNone(decodificar_jpeg(b'no es imagen'))
