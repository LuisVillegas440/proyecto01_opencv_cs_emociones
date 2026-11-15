"""Vistas de la app de emociones.

- camara: página que captura video desde el navegador.
- iniciar_sesion / finalizar_sesion: abren y cierran una SesionAnalisis.
- analizar: recibe un frame JPEG, detecta rostros (YuNet), reconoce la
  emoción de cada uno (FER+) y devuelve el resultado en JSON. Si llega el id
  de una sesión en curso, guarda los resultados (máx. 1 muestra/segundo).
- historial / detalle_sesion / exportar_csv: consulta de sesiones guardadas.
"""
import csv
import re
import time

from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from . import estadisticas
from .models import SesionAnalisis
from .presentacion import PRESENTACION, info
from .registro import guardar_resultados, olvidar_sesion
from .servicios import obtener_analizador
from .vision import EMOCIONES, decodificar_jpeg

# Límite de tamaño de un frame para evitar abusos (2 MB).
TAMANO_MAXIMO_FRAME = 2 * 1024 * 1024
PATRON_CLIENTE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
NOMBRE_POR_DEFECTO = 'Sesión sin nombre'


def error(mensaje, status=400):
    return JsonResponse({'ok': False, 'error': mensaje}, status=status)


def sesion_en_curso(valor):
    """Devuelve la SesionAnalisis abierta con ese id, o None."""
    if not str(valor or '').isdigit():
        return None
    return SesionAnalisis.objects.filter(pk=int(valor), fin__isnull=True).first()


def camara(request):
    """Muestra la página con la cámara en vivo."""
    return render(request, 'emociones/camara.html', {'presentacion': PRESENTACION})


@require_POST
def iniciar_sesion(request):
    """Crea una sesión de análisis y devuelve su id."""
    nombre = request.POST.get('nombre', '').strip()[:120] or NOMBRE_POR_DEFECTO
    sesion = SesionAnalisis.objects.create(nombre=nombre)
    return JsonResponse({'ok': True, 'sesion': sesion.pk, 'nombre': sesion.nombre})


@require_POST
def finalizar_sesion(request, pk):
    """Marca la hora de fin de una sesión (idempotente)."""
    sesion = SesionAnalisis.objects.filter(pk=pk).first()
    if sesion is None:
        return error('La sesión no existe.', 404)
    sesion.finalizar()
    olvidar_sesion(sesion.pk)
    return JsonResponse({'ok': True, 'sesion': sesion.pk, 'registros': sesion.registros.count()})


@require_POST
def analizar(request):
    """Recibe un frame (campo 'frame', JPEG) y devuelve los rostros y emociones.

    Campos opcionales:
    - 'cliente': id de la pestaña, para suavizar resultados entre frames.
    - 'sesion': id de una sesión en curso, para guardar los resultados.
    """
    inicio = time.perf_counter()

    archivo = request.FILES.get('frame')
    if archivo is None:
        return error('Falta el campo "frame".')
    if archivo.size > TAMANO_MAXIMO_FRAME:
        return error('El frame es demasiado grande.', 413)

    frame = decodificar_jpeg(archivo.read())
    if frame is None:
        return error('No se pudo decodificar la imagen.')

    cliente = request.POST.get('cliente', '')
    if not PATRON_CLIENTE.match(cliente):
        cliente = None

    rostros = obtener_analizador().analizar(frame, cliente)

    guardados = 0
    sesion = sesion_en_curso(request.POST.get('sesion'))
    if sesion is not None:
        guardados = guardar_resultados(sesion, rostros)

    alto, ancho = frame.shape[:2]
    return JsonResponse({
        'ok': True,
        'ancho': ancho,
        'alto': alto,
        'rostros': rostros,
        'guardados': guardados,
        'ms': round((time.perf_counter() - inicio) * 1000, 1),
    })


# --- Historial ----------------------------------------------------------------

def historial(request):
    """Lista paginada de sesiones con su resumen."""
    sesiones = (SesionAnalisis.objects
                .annotate(total=Count('registros'), rostros=Count('registros__rostro_id', distinct=True))
                .order_by('-inicio'))
    pagina = Paginator(sesiones, 15).get_page(request.GET.get('pagina'))
    for sesion in pagina:
        emocion = sesion.emocion_predominante()
        sesion.predominante_info = info(emocion) if emocion else None
        sesion.duracion_texto = estadisticas.formato_tiempo(sesion.duracion.total_seconds())
    return render(request, 'emociones/historial.html', {'pagina': pagina})


def detalle_sesion(request, pk):
    """Estadísticas y gráficos de una sesión."""
    sesion = get_object_or_404(SesionAnalisis, pk=pk)
    registros = sesion.registros.order_by('momento').only(
        'momento', 'rostro_id', 'emocion', 'confianza')
    datos = estadisticas.calcular(sesion, registros)
    datos_grafico = {
        'emociones': [
            {'clave': e, **PRESENTACION[e]} for e in EMOCIONES
        ],
        'distribucion': [d['total'] for d in datos['distribucion']],
        'linea_tiempo': datos['linea_tiempo'],
    }
    return render(request, 'emociones/sesion_detalle.html', {
        'sesion': sesion,
        'est': datos,
        'datos_grafico': datos_grafico,
    })


def exportar_csv(request, pk):
    """Descarga todos los registros de la sesión en CSV (UTF-8 con BOM para Excel)."""
    sesion = get_object_or_404(SesionAnalisis, pk=pk)
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    nombre = slugify(sesion.nombre) or 'sesion'
    respuesta['Content-Disposition'] = f'attachment; filename="sesion_{sesion.pk}_{nombre}.csv"'
    respuesta.write('\ufeff')  # BOM: Excel reconoce tildes y emojis

    escritor = csv.writer(respuesta)
    escritor.writerow(['sesion', 'momento', 'segundos_desde_inicio', 'rostro_id',
                       'emocion', 'confianza', *[f'prob_{e}' for e in EMOCIONES]])
    for r in sesion.registros.order_by('momento').iterator():
        escritor.writerow([
            sesion.nombre,
            timezone.localtime(r.momento).strftime('%Y-%m-%d %H:%M:%S'),
            round((r.momento - sesion.inicio).total_seconds(), 1),
            r.rostro_id,
            r.emocion,
            r.confianza,
            *[r.probabilidades.get(e, '') for e in EMOCIONES],
        ])
    return respuesta
