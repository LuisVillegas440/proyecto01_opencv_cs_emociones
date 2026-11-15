"""Reconocimiento de emociones con el modelo FER+ (ONNX Model Zoo).

Entrada del modelo: imagen en escala de grises de 64x64, valores 0-255,
forma 1x1x64x64. Salida: 8 puntuaciones (logits), una por emoción.
"""
from pathlib import Path

import cv2
import numpy as np

# Orden de las clases definido por el modelo FER+.
EMOCIONES = [
    'neutral', 'felicidad', 'sorpresa', 'tristeza',
    'enojo', 'disgusto', 'miedo', 'desprecio',
]

TAMANO_ENTRADA = 64


def softmax(logits: np.ndarray) -> np.ndarray:
    """Convierte puntuaciones en probabilidades (fila a fila)."""
    exp = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return exp / exp.sum(axis=-1, keepdims=True)


class ClasificadorEmociones:
    """Clasifica la emoción de uno o varios recortes de rostro."""

    def __init__(self, ruta_modelo, usar_clahe=True):
        ruta_modelo = Path(ruta_modelo)
        if not ruta_modelo.exists():
            raise FileNotFoundError(f'No se encontró el modelo FER+: {ruta_modelo}')
        self._red = cv2.dnn.readNetFromONNX(str(ruta_modelo))
        # CLAHE: ecualización adaptativa del histograma. Mejora el contraste
        # del rostro cuando hay poca luz o iluminación lateral.
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)) if usar_clahe else None

    def preprocesar(self, rostro_bgr: np.ndarray) -> np.ndarray:
        """Recorte BGR -> gris 64x64 (uint8) listo para el modelo."""
        gris = cv2.cvtColor(rostro_bgr, cv2.COLOR_BGR2GRAY)
        gris = cv2.resize(gris, (TAMANO_ENTRADA, TAMANO_ENTRADA), interpolation=cv2.INTER_AREA)
        if self._clahe is not None:
            gris = self._clahe.apply(gris)
        return gris

    def clasificar_lote(self, recortes_bgr: list[np.ndarray]) -> np.ndarray:
        """Clasifica varios rostros en una sola pasada.

        Devuelve una matriz (n_rostros, 8) de probabilidades.
        """
        if not recortes_bgr:
            return np.empty((0, len(EMOCIONES)), dtype=np.float32)
        entradas = [self.preprocesar(r).astype(np.float32) for r in recortes_bgr]
        blob = cv2.dnn.blobFromImages(entradas)  # (n, 1, 64, 64), sin normalizar
        self._red.setInput(blob)
        logits = self._red.forward().reshape(len(entradas), -1)
        return softmax(logits)

    def clasificar(self, rostro_bgr: np.ndarray) -> dict[str, float]:
        """Clasifica un solo rostro y devuelve {emoción: probabilidad}."""
        probs = self.clasificar_lote([rostro_bgr])[0]
        return dict(zip(EMOCIONES, map(float, probs)))
