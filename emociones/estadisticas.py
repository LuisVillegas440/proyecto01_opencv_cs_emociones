"""Estadísticas de una sesión de análisis a partir de sus registros.

Funciones puras (sin consultas a la base), fáciles de probar.
"""
import math
from collections import Counter, defaultdict

from .presentacion import PRESENTACION
from .vision import EMOCIONES

PUNTOS_MAXIMOS_GRAFICO = 60  # cantidad máxima de puntos en la línea de tiempo


def porcentaje(parte, total):
    return round(100 * parte / total, 1) if total else 0.0


def formato_tiempo(segundos):
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, seg = divmod(resto, 60)
    return f'{horas}:{minutos:02d}:{seg:02d}' if horas else f'{minutos:02d}:{seg:02d}'


def predominante(contador: Counter):
    return contador.most_common(1)[0][0] if contador else None


def linea_de_tiempo(registros, inicio):
    """Porcentaje de cada emoción por intervalo de tiempo desde el inicio.

    El tamaño del intervalo se adapta a la duración para no superar
    PUNTOS_MAXIMOS_GRAFICO puntos.
    """
    if not registros:
        return {'intervalo_s': 0, 'etiquetas': [], 'series': {e: [] for e in EMOCIONES}}

    duracion = max((r.momento - inicio).total_seconds() for r in registros)
    intervalo = max(1, math.ceil((duracion + 1) / PUNTOS_MAXIMOS_GRAFICO))

    por_intervalo = defaultdict(Counter)
    for r in registros:
        indice = int(max(0, (r.momento - inicio).total_seconds()) // intervalo)
        por_intervalo[indice][r.emocion] += 1

    indices = range(max(por_intervalo) + 1)
    series = {e: [] for e in EMOCIONES}
    for i in indices:
        conteo = por_intervalo.get(i, Counter())
        total = sum(conteo.values())
        for e in EMOCIONES:
            # None deja un hueco en el gráfico cuando no hubo rostros.
            series[e].append(porcentaje(conteo[e], total) if total else None)

    return {
        'intervalo_s': intervalo,
        'etiquetas': [formato_tiempo(i * intervalo) for i in indices],
        'series': series,
    }


def resumen_por_rostro(registros):
    grupos = defaultdict(list)
    for r in registros:
        grupos[r.rostro_id].append(r)
    filas = []
    for rostro_id, lista in sorted(grupos.items()):
        conteo = Counter(r.emocion for r in lista)
        emocion = predominante(conteo)
        filas.append({
            'rostro_id': rostro_id,
            'registros': len(lista),
            'emocion': emocion,
            'info': PRESENTACION[emocion],
            'porcentaje': porcentaje(conteo[emocion], len(lista)),
            'confianza_media': round(sum(r.confianza for r in lista) / len(lista), 3),
            'primera': min(r.momento for r in lista),
            'ultima': max(r.momento for r in lista),
        })
    return filas


def calcular(sesion, registros):
    """Resumen completo de una sesión. `registros` es una lista de RegistroEmocion."""
    registros = list(registros)
    total = len(registros)
    conteo = Counter(r.emocion for r in registros)
    emocion = predominante(conteo)

    tonos = Counter(PRESENTACION[r.emocion]['tono'] for r in registros)
    # Rostros vistos a la vez: registros que comparten el mismo segundo.
    por_segundo = Counter(r.momento.replace(microsecond=0) for r in registros)

    return {
        'total': total,
        'duracion': formato_tiempo(sesion.duracion.total_seconds()),
        'predominante': emocion,
        'predominante_info': PRESENTACION[emocion] if emocion else None,
        'predominante_pct': porcentaje(conteo[emocion], total) if emocion else 0,
        'rostros_distintos': len({r.rostro_id for r in registros}),
        'rostros_max': max(por_segundo.values(), default=0),
        'confianza_media': round(sum(r.confianza for r in registros) / total, 3) if total else 0,
        'animo': {t: porcentaje(tonos[t], total) for t in ('positivo', 'neutro', 'negativo')},
        'distribucion': [
            {'emocion': e, 'info': PRESENTACION[e], 'total': conteo[e],
             'porcentaje': porcentaje(conteo[e], total)}
            for e in EMOCIONES
        ],
        'linea_tiempo': linea_de_tiempo(registros, sesion.inicio),
        'por_rostro': resumen_por_rostro(registros),
    }
