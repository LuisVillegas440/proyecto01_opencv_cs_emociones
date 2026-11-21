"""Pruebas unitarias del seguimiento de rostros entre frames y el suavizado (EMA)."""
import numpy as np
from django.test import SimpleTestCase

from emociones.vision import SeguidorRostros
from emociones.vision.seguimiento import iou


class SeguimientoTests(SimpleTestCase):
    def test_iou(self):
        """El solapamiento (IoU) es 1 para cajas iguales y 0 para cajas separadas."""
        self.assertEqual(iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)
        self.assertEqual(iou([0, 0, 10, 10], [20, 20, 5, 5]), 0.0)

    def test_mantiene_id_y_suaviza(self):
        """Un rostro que se mueve poco conserva su id y sus probabilidades se suavizan."""
        seguidor = SeguidorRostros(alfa=0.5)
        p1 = np.eye(8)[0]  # 100% neutral
        p2 = np.eye(8)[1]  # 100% felicidad
        id1 = seguidor.actualizar([[10, 10, 50, 50]], np.array([p1]))[0].id
        pista = seguidor.actualizar([[12, 11, 50, 50]], np.array([p2]))[0]
        self.assertEqual(pista.id, id1)                 # mismo rostro, mismo id
        self.assertAlmostEqual(pista.probs[0], 0.5)     # promedio suavizado
        self.assertAlmostEqual(pista.probs[1], 0.5)

    def test_rostro_lejano_es_nuevo(self):
        """Un rostro en otra posición recibe un id nuevo."""
        seguidor = SeguidorRostros()
        p = np.array([np.eye(8)[0]])
        a = seguidor.actualizar([[0, 0, 40, 40]], p)[0].id
        b = seguidor.actualizar([[300, 300, 40, 40]], p)[0].id
        self.assertNotEqual(a, b)

    def test_descarta_pistas_perdidas(self):
        """Un rostro que deja de verse se descarta tras varios frames."""
        seguidor = SeguidorRostros(max_frames_perdido=2)
        seguidor.actualizar([[0, 0, 40, 40]], np.array([np.eye(8)[0]]))
        for _ in range(3):
            seguidor.actualizar([], np.empty((0, 8)))
        self.assertEqual(seguidor.pistas, [])
