"""Pipeline completo: frame JPEG -> rostros -> emociones -> resultado suavizado."""
import threading
import time
from collections import OrderedDict

import cv2
import numpy as np

from .clasificador import EMOCIONES, ClasificadorEmociones
from .detector_rostros import DetectorRostros
from .seguimiento import SeguidorRostros

# Margen extra alrededor de la caja de YuNet (fracción del tamaño del rostro);
# FER+ fue entrenado con rostros que incluyen algo de frente y mentón.
MARGEN_RECORTE = 0.1


def decodificar_jpeg(datos: bytes):
    """Bytes de imagen -> frame BGR, o None si no es una imagen válida."""
    if not datos:
        return None
    return cv2.imdecode(np.frombuffer(datos, dtype=np.uint8), cv2.IMREAD_COLOR)


def recortar_con_margen(frame, caja, margen=MARGEN_RECORTE):
    x, y, w, h = caja
    alto, ancho = frame.shape[:2]
    dx, dy = int(w * margen), int(h * margen)
    x0, y0 = max(x - dx, 0), max(y - dy, 0)
    x1, y1 = min(x + w + dx, ancho), min(y + h + dy, alto)
    return frame[y0:y1, x0:x1]


class AnalizadorEmociones:
    """Orquesta detección + reconocimiento + seguimiento.

    Es seguro para usar desde varios hilos (el servidor de Django atiende
    peticiones en paralelo y las redes de OpenCV no son thread-safe).
    Mantiene un seguidor de rostros por cliente (pestaña del navegador).
    """

    MAX_CLIENTES = 50
    SEGUNDOS_INACTIVIDAD = 60

    def __init__(self, ruta_yunet, ruta_ferplus, umbral_rostro=0.8):
        self.detector = DetectorRostros(ruta_yunet, umbral=umbral_rostro)
        self.clasificador = ClasificadorEmociones(ruta_ferplus)
        self._lock = threading.Lock()
        self._seguidores: OrderedDict[str, tuple[SeguidorRostros, float]] = OrderedDict()

    def _seguidor(self, cliente: str) -> SeguidorRostros:
        ahora = time.monotonic()
        seguidor, _ = self._seguidores.pop(cliente, (None, 0))
        if seguidor is None:
            seguidor = SeguidorRostros()
        self._seguidores[cliente] = (seguidor, ahora)
        # Limpiar clientes inactivos o en exceso (los más antiguos van primero).
        while self._seguidores:
            clave, (_, visto) = next(iter(self._seguidores.items()))
            if len(self._seguidores) > self.MAX_CLIENTES or ahora - visto > self.SEGUNDOS_INACTIVIDAD:
                self._seguidores.pop(clave)
            else:
                break
        return seguidor

    def analizar(self, frame_bgr, cliente: str | None = None) -> list[dict]:
        """Analiza un frame y devuelve una lista de rostros con su emoción."""
        with self._lock:
            rostros = self.detector.detectar(frame_bgr)
            recortes = [recortar_con_margen(frame_bgr, r.caja) for r in rostros]
            probs = self.clasificador.clasificar_lote(recortes)

            if cliente:
                pistas = self._seguidor(cliente).actualizar([r.caja for r in rostros], probs)
                ids = [p.id for p in pistas]
                probs = np.array([p.probs for p in pistas]) if pistas else probs
            else:
                ids = list(range(1, len(rostros) + 1))

        resultados = []
        for rostro, ident, p in zip(rostros, ids, probs):
            indice = int(np.argmax(p))
            resultados.append({
                'id': ident,
                'caja': rostro.caja,
                'confianza_rostro': round(rostro.confianza, 3),
                'emocion': EMOCIONES[indice],
                'confianza': round(float(p[indice]), 3),
                'probabilidades': {e: round(float(v), 3) for e, v in zip(EMOCIONES, p)},
            })
        return resultados
