"""Cómo se muestra cada emoción en la interfaz (etiqueta, emoji, color, tono).

Fuente única para las plantillas, los gráficos y el JavaScript de la cámara.
El 'tono' agrupa emociones para el índice de ánimo: positivo, neutro o negativo.
"""
from .vision import EMOCIONES

PRESENTACION = {
    'neutral':   {'etiqueta': 'Neutral',   'emoji': '😐', 'color': '#94a3b8', 'tono': 'neutro'},
    'felicidad': {'etiqueta': 'Felicidad', 'emoji': '😄', 'color': '#22c55e', 'tono': 'positivo'},
    'sorpresa':  {'etiqueta': 'Sorpresa',  'emoji': '😮', 'color': '#eab308', 'tono': 'neutro'},
    'tristeza':  {'etiqueta': 'Tristeza',  'emoji': '😢', 'color': '#3b82f6', 'tono': 'negativo'},
    'enojo':     {'etiqueta': 'Enojo',     'emoji': '😠', 'color': '#ef4444', 'tono': 'negativo'},
    'disgusto':  {'etiqueta': 'Disgusto',  'emoji': '🤢', 'color': '#84cc16', 'tono': 'negativo'},
    'miedo':     {'etiqueta': 'Miedo',     'emoji': '😨', 'color': '#a855f7', 'tono': 'negativo'},
    'desprecio': {'etiqueta': 'Desprecio', 'emoji': '😒', 'color': '#f97316', 'tono': 'negativo'},
}

assert list(PRESENTACION) == EMOCIONES, 'PRESENTACION debe seguir el orden del modelo'


def info(emocion):
    """Presentación de una emoción (o de 'neutral' si es desconocida)."""
    return PRESENTACION.get(emocion, PRESENTACION['neutral'])
