"""Datos de prueba compartidos por las pruebas unitarias y de integración."""
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile

from emociones.models import RegistroEmocion, SesionAnalisis

# Imagen real con un rostro (muestra messi5.jpg de los ejemplos de OpenCV).
IMAGEN_ROSTRO = Path(__file__).parent / 'imagenes' / 'con_rostro.jpg'


def jpeg_de_prueba(ancho=320, alto=240):
    """Genera un JPEG sintético (gris, sin rostros) en memoria."""
    imagen = np.full((alto, ancho, 3), 127, dtype=np.uint8)
    ok, buffer = cv2.imencode('.jpg', imagen)
    assert ok
    return SimpleUploadedFile('frame.jpg', buffer.tobytes(), content_type='image/jpeg')


def frame_con_rostro():
    """La imagen con rostro como archivo subido, lista para enviar a la API."""
    return SimpleUploadedFile('frame.jpg', IMAGEN_ROSTRO.read_bytes(), content_type='image/jpeg')


def crear_sesion_con_datos(nombre='Clase de prueba'):
    """Sesión de 10 s: rostro 1 feliz los primeros 6 s y triste después; rostro 2 neutral."""
    sesion = SesionAnalisis.objects.create(nombre=nombre)
    sesion.fin = sesion.inicio + timedelta(seconds=10)
    sesion.save()
    registros = []
    for s in range(10):
        momento = sesion.inicio + timedelta(seconds=s)
        emocion = 'felicidad' if s < 6 else 'tristeza'
        registros.append(RegistroEmocion(sesion=sesion, momento=momento, rostro_id=1,
                                         emocion=emocion, confianza=0.8,
                                         probabilidades={emocion: 0.8, 'neutral': 0.2}))
        if s < 4:
            registros.append(RegistroEmocion(sesion=sesion, momento=momento, rostro_id=2,
                                             emocion='neutral', confianza=0.6,
                                             probabilidades={'neutral': 0.6}))
    RegistroEmocion.objects.bulk_create(registros)
    return sesion
