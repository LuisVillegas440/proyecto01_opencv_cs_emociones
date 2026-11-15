"""Detección de rostros con YuNet (cv2.FaceDetectorYN).

YuNet es un detector ligero basado en CNN incluido en OpenCV Zoo. Es mucho
más preciso que los clasificadores Haar ante giros de cabeza y poca luz.
"""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class Rostro:
    """Un rostro detectado, en coordenadas de píxeles del frame."""
    x: int
    y: int
    ancho: int
    alto: int
    confianza: float

    @property
    def caja(self):
        return [self.x, self.y, self.ancho, self.alto]


class DetectorRostros:
    """Envuelve YuNet y devuelve rostros recortados a los límites del frame."""

    def __init__(self, ruta_modelo, umbral=0.8, umbral_nms=0.3, tamano_minimo=24):
        ruta_modelo = Path(ruta_modelo)
        if not ruta_modelo.exists():
            raise FileNotFoundError(f'No se encontró el modelo YuNet: {ruta_modelo}')
        self.tamano_minimo = tamano_minimo
        self._detector = cv2.FaceDetectorYN.create(
            str(ruta_modelo), '', (320, 320), umbral, umbral_nms, 5000,
        )
        self._tamano_actual = None

    def detectar(self, frame_bgr: np.ndarray) -> list[Rostro]:
        """Detecta rostros en un frame BGR. Devuelve lista ordenada por tamaño."""
        alto, ancho = frame_bgr.shape[:2]
        if self._tamano_actual != (ancho, alto):
            # YuNet necesita conocer el tamaño de entrada; solo se actualiza si cambia.
            self._detector.setInputSize((ancho, alto))
            self._tamano_actual = (ancho, alto)

        _, detecciones = self._detector.detect(frame_bgr)
        if detecciones is None:
            return []

        rostros = []
        for fila in detecciones:
            x, y, w, h = fila[:4]
            # Recortar la caja a los bordes de la imagen.
            x0, y0 = max(int(x), 0), max(int(y), 0)
            x1, y1 = min(int(x + w), ancho), min(int(y + h), alto)
            if x1 - x0 < self.tamano_minimo or y1 - y0 < self.tamano_minimo:
                continue
            rostros.append(Rostro(x0, y0, x1 - x0, y1 - y0, float(fila[-1])))

        rostros.sort(key=lambda r: r.ancho * r.alto, reverse=True)
        return rostros
