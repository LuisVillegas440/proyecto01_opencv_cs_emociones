"""Guardado de resultados en la base de datos, limitado a 1 muestra por segundo.

El análisis corre ~6 veces por segundo; guardar todo llenaría la base sin
aportar información. Se guarda como máximo una muestra por sesión y segundo.
"""
import threading
import time

from .models import RegistroEmocion

INTERVALO_GUARDADO = 1.0  # segundos

_ultimo_guardado: dict[int, float] = {}
_lock = threading.Lock()


def toca_guardar(sesion_id: int) -> bool:
    """True si pasó al menos INTERVALO_GUARDADO desde el último guardado de la sesión."""
    ahora = time.monotonic()
    with _lock:
        if ahora - _ultimo_guardado.get(sesion_id, 0.0) < INTERVALO_GUARDADO:
            return False
        _ultimo_guardado[sesion_id] = ahora
        return True


def olvidar_sesion(sesion_id: int) -> None:
    with _lock:
        _ultimo_guardado.pop(sesion_id, None)


def guardar_resultados(sesion, rostros: list[dict]) -> int:
    """Guarda un registro por rostro si corresponde. Devuelve cuántos guardó."""
    if not rostros or not toca_guardar(sesion.pk):
        return 0
    RegistroEmocion.objects.bulk_create([
        RegistroEmocion(
            sesion=sesion,
            rostro_id=r['id'],
            emocion=r['emocion'],
            confianza=r['confianza'],
            probabilidades=r['probabilidades'],
        )
        for r in rostros
    ])
    return len(rostros)
