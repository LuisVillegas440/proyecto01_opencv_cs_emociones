"""Punto único de acceso al analizador de emociones.

Los modelos se cargan una sola vez (la primera petición) y se reutilizan
en todas las siguientes, porque cargarlos tarda cientos de milisegundos.
"""
import threading

import cv2
from django.conf import settings

from .vision import AnalizadorEmociones

# OpenCV 5 muestra un aviso inofensivo al cargar YuNet; solo mostramos errores.
cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)

_analizador = None
_lock = threading.Lock()


def obtener_analizador() -> AnalizadorEmociones:
    global _analizador
    if _analizador is None:
        with _lock:
            if _analizador is None:
                _analizador = AnalizadorEmociones(
                    settings.MODELO_ROSTROS,
                    settings.MODELO_EMOCIONES,
                    umbral_rostro=settings.UMBRAL_ROSTRO,
                )
    return _analizador
