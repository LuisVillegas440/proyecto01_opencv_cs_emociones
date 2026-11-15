"""Módulo de visión por computadora (OpenCV), independiente de Django.

Componentes:
- detector_rostros.DetectorRostros: localiza rostros con YuNet.
- clasificador.ClasificadorEmociones: reconoce la emoción con FER+ (ONNX).
- seguimiento.SeguidorRostros: asocia rostros entre frames y suaviza resultados.
- pipeline.AnalizadorEmociones: une todo: bytes JPEG -> lista de resultados.
"""
from .clasificador import EMOCIONES, ClasificadorEmociones
from .detector_rostros import DetectorRostros, Rostro
from .pipeline import AnalizadorEmociones, decodificar_jpeg
from .seguimiento import SeguidorRostros

__all__ = [
    'EMOCIONES', 'ClasificadorEmociones', 'DetectorRostros', 'Rostro',
    'AnalizadorEmociones', 'decodificar_jpeg', 'SeguidorRostros',
]
