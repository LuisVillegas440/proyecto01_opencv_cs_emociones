"""Ejecuta todas las pruebas con medición de cobertura y genera el reporte de pruebas.

Uso (desde la raíz del proyecto, con el entorno virtual activo):

    pip install -r requirements-dev.txt
    python herramientas/reporte_pruebas.py

Genera en `evidencias/`:
    reporte_pruebas.html       Resumen por tipo, detalle de cada prueba, cobertura y capturas
    log_pruebas.txt            Salida completa de la ejecución (log)
    resultados.json            Resultados y cobertura en formato JSON
    cobertura.txt              Cobertura por archivo en texto
    cobertura_html/index.html  Cobertura línea por línea (coverage.py)
    funcionales/*.png          Capturas tomadas por las pruebas funcionales

Devuelve código de salida 1 si alguna prueba falla, para poder usarlo en integración continua.
"""
import base64
import html
import io
import json
import os
import platform
import re
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / 'evidencias'
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

import coverage  # noqa: E402

# La cobertura debe empezar ANTES de importar Django y la app, para medir también
# las líneas que se ejecutan al importar (definiciones de clases y funciones).
cobertura = coverage.Coverage(config_file=str(RAIZ / '.coveragerc'))
cobertura.start()

import django  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test.runner import DiscoverRunner  # noqa: E402

TIPOS = [('unitarias', 'Unitarias'), ('integracion', 'Integración'), ('funcionales', 'Funcionales')]
ESTADOS = {'aprobada': 'Aprobada', 'fallida': 'Fallida', 'error': 'Error', 'omitida': 'Omitida'}


# --- Ejecución de las pruebas registrando cada resultado ---------------------------
class Duplicador(io.TextIOBase):
    """Escribe a la vez en la consola y en el archivo de log."""

    def __init__(self, *destinos):
        self.destinos = destinos

    def write(self, texto):
        for d in self.destinos:
            d.write(texto)
        return len(texto)

    def flush(self):
        for d in self.destinos:
            d.flush()


class ResultadoRegistrado(unittest.TextTestResult):
    registros = []

    def startTest(self, test):
        self._inicio = time.perf_counter()
        super().startTest(test)

    def _registrar(self, test, estado, detalle=''):
        inicio = getattr(self, '_inicio', time.perf_counter())
        descripcion = getattr(test, 'shortDescription', lambda: None)()
        self.registros.append({
            'id': test.id(), 'descripcion': descripcion, 'estado': estado, 'detalle': detalle,
            'segundos': time.perf_counter() - inicio,
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._registrar(test, 'aprobada')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._registrar(test, 'fallida', self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._registrar(test, 'error', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._registrar(test, 'omitida', reason)


class EjecutorConReporte(DiscoverRunner):
    def __init__(self, flujo, **kwargs):
        super().__init__(**kwargs)
        self.flujo = flujo

    def get_resultclass(self):
        return ResultadoRegistrado

    def get_test_runner_kwargs(self):
        kwargs = super().get_test_runner_kwargs()
        kwargs['stream'] = self.flujo
        return kwargs


def ejecutar_pruebas(archivo_log):
    flujo = Duplicador(sys.stderr, archivo_log)
    flujo.write(f'Reporte de pruebas de EmoVisión · {datetime.now():%d/%m/%Y %H:%M:%S}\n')
    flujo.write('Comando: python manage.py test emociones -v 2 (con medición de cobertura)\n')
    flujo.write('=' * 78 + '\n')
    inicio = time.perf_counter()
    fallos = EjecutorConReporte(flujo, verbosity=2).run_tests(['emociones'])
    return fallos, time.perf_counter() - inicio


# --- Datos para el reporte -----------------------------------------------------------
def tipo_de(id_prueba):
    for clave, nombre in TIPOS:
        if f'.tests.{clave}.' in id_prueba:
            return nombre
    return 'Otras'


def nombre_legible(id_prueba):
    metodo = id_prueba.rsplit('.', 1)[-1]
    texto = re.sub(r'^test_', '', metodo)
    texto = re.sub(r'^cu(\d+)_', r'CU-\1 · ', texto)
    texto = texto.replace('_', ' ')
    return texto[:1].upper() + texto[1:]


def archivo_y_clase(id_prueba):
    partes = id_prueba.split('.')
    if len(partes) < 3:
        return id_prueba, ''
    return f'{partes[-3]}.py', partes[-2]


def datos_cobertura():
    filas = []
    for archivo in sorted(cobertura.get_data().measured_files()):
        _, sentencias, _, faltantes, texto_faltantes = cobertura.analysis2(archivo)
        if not sentencias:
            continue
        relativo = Path(archivo).resolve().relative_to(RAIZ).as_posix()
        cubiertas = len(sentencias) - len(faltantes)
        filas.append({'archivo': relativo, 'sentencias': len(sentencias), 'faltantes': len(faltantes),
                      'porcentaje': 100 * cubiertas / len(sentencias), 'lineas': texto_faltantes})
    return filas


def entorno():
    import cv2
    import numpy

    from emociones.tests.funcionales.base import NAVEGADOR_USADO
    try:
        from importlib.metadata import version
        playwright = version('playwright')
    except Exception:
        playwright = 'no instalado'
    navegador = (f"{NAVEGADOR_USADO['nombre']} {NAVEGADOR_USADO['version']}"
                 if NAVEGADOR_USADO else 'no utilizado')
    return [
        ('Fecha de ejecución', f'{datetime.now():%d/%m/%Y %H:%M:%S}'),
        ('Sistema operativo', platform.platform()),
        ('Python', platform.python_version()),
        ('Django', django.get_version()),
        ('OpenCV', cv2.__version__),
        ('NumPy', numpy.__version__),
        ('coverage.py', coverage.__version__),
        ('Playwright', playwright),
        ('Navegador (pruebas funcionales)', navegador),
    ]


# --- Reporte HTML --------------------------------------------------------------------
ESTILO = """
:root { --marino:#13334c; --marino-oscuro:#0e2433; --naranja:#f7941d; --fondo:#f4f6f9;
        --borde:#dde3ea; --suave:#5b6b7b; --ok:#15803d; --mal:#dc2626; --omit:#a16207; }
* { box-sizing:border-box; }
body { margin:0; font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; background:var(--fondo); color:var(--marino); }
header { background:var(--marino-oscuro); color:#fff; padding:1.25rem 2rem; border-bottom:3px solid var(--naranja); }
header h1 { margin:0; font-size:1.5rem; } header p { margin:.3rem 0 0; color:#c7d2dc; }
main { max-width:1150px; margin:0 auto; padding:1.5rem 1rem 3rem; }
h2 { font-size:1.15rem; margin:2rem 0 .75rem; padding-left:.6rem; border-left:4px solid var(--naranja); }
.tarjetas { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.9rem; }
.tarjeta { background:#fff; border:1px solid var(--borde); border-top:4px solid var(--marino); border-radius:10px; padding:.9rem 1rem; }
.tarjeta span { display:block; font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; color:var(--suave); }
.tarjeta b { font-size:1.6rem; }
.tarjeta.ok { border-top-color:var(--ok); } .tarjeta.ok b { color:var(--ok); }
.tarjeta.mal { border-top-color:var(--mal); } .tarjeta.mal b { color:var(--mal); }
.tarjeta.naranja { border-top-color:var(--naranja); }
.veredicto { margin:1rem 0 0; padding:.8rem 1rem; border-radius:10px; font-weight:700; }
.veredicto.ok { background:#dcfce7; color:var(--ok); } .veredicto.mal { background:#fee2e2; color:var(--mal); }
.tabla { overflow-x:auto; border:1px solid var(--borde); border-radius:10px; background:#fff; }
table { width:100%; border-collapse:collapse; font-size:.88rem; }
th { background:var(--marino); color:#fff; text-align:left; font-weight:600; font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; }
th, td { padding:.5rem .75rem; border-bottom:1px solid var(--borde); vertical-align:top; }
tr:last-child td { border-bottom:none; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
code { font-family:Consolas,monospace; font-size:.82rem; color:var(--suave); }
.estado { font-weight:700; white-space:nowrap; }
.aprobada { color:var(--ok); } .fallida, .error { color:var(--mal); } .omitida { color:var(--omit); }
pre { white-space:pre-wrap; font-size:.75rem; background:#fff7ed; padding:.5rem; border-radius:6px; margin:.4rem 0 0; }
.barra { height:8px; background:#e8edf2; border-radius:4px; overflow:hidden; min-width:80px; }
.barra i { display:block; height:100%; background:var(--ok); }
.barra i.media { background:var(--naranja); } .barra i.baja { background:var(--mal); }
.capturas { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:1rem; }
figure { margin:0; background:#fff; border:1px solid var(--borde); border-radius:10px; overflow:hidden; }
figure img { width:100%; display:block; border-bottom:1px solid var(--borde); }
figcaption { padding:.5rem .75rem; font-size:.85rem; font-weight:600; }
.nota { color:var(--suave); font-size:.85rem; }
"""


def e(texto):
    return html.escape(str(texto))


def generar_html(registros, segundos, filas_cob, total_cob, info):
    totales = {k: sum(r['estado'] == k for r in registros) for k in ESTADOS}
    total = len(registros)
    exito = totales['fallida'] == 0 and totales['error'] == 0
    partes = [f'<title>Reporte de pruebas · EmoVisión</title><style>{ESTILO}</style>',
              '<header><h1>Reporte de pruebas · EmoVisión</h1>',
              f'<p>Generado el {e(info[0][1])} con <code>python herramientas/reporte_pruebas.py</code></p></header><main>']

    # Resumen general
    partes.append('<h2>Resumen</h2><div class="tarjetas">')
    for titulo, valor, clase in [
        ('Pruebas ejecutadas', total, ''),
        ('Aprobadas', totales['aprobada'], 'ok'),
        ('Fallidas / con error', totales['fallida'] + totales['error'], 'mal' if not exito else ''),
        ('Omitidas', totales['omitida'], ''),
        ('Tiempo total', f'{segundos:.1f} s', ''),
        ('Cobertura de código', f'{total_cob:.0f} %', 'naranja'),
    ]:
        partes.append(f'<div class="tarjeta {clase}"><span>{e(titulo)}</span><b>{e(valor)}</b></div>')
    partes.append('</div>')
    partes.append(f'<p class="veredicto {"ok" if exito else "mal"}">'
                  + ('✔ Todas las pruebas ejecutadas fueron exitosas.' if exito
                     else '✘ Hay pruebas que fallaron; ver el detalle más abajo.') + '</p>')

    # Por tipo
    partes.append('<h2>Resultados por tipo de prueba</h2><div class="tabla"><table><tr><th>Tipo</th>'
                  '<th class="num">Total</th><th class="num">Aprobadas</th><th class="num">Fallidas</th>'
                  '<th class="num">Omitidas</th><th class="num">Tiempo</th></tr>')
    for _, nombre in TIPOS:
        grupo = [r for r in registros if tipo_de(r['id']) == nombre]
        if not grupo:
            continue
        partes.append(
            f'<tr><td><b>{e(nombre)}</b></td><td class="num">{len(grupo)}</td>'
            f'<td class="num aprobada">{sum(r["estado"] == "aprobada" for r in grupo)}</td>'
            f'<td class="num fallida">{sum(r["estado"] in ("fallida", "error") for r in grupo)}</td>'
            f'<td class="num omitida">{sum(r["estado"] == "omitida" for r in grupo)}</td>'
            f'<td class="num">{sum(r["segundos"] for r in grupo):.2f} s</td></tr>')
    partes.append('</table></div>')

    # Detalle
    for _, nombre in TIPOS:
        grupo = sorted((r for r in registros if tipo_de(r['id']) == nombre), key=lambda r: r['id'])
        if not grupo:
            continue
        partes.append(f'<h2>Detalle · pruebas {e(nombre.lower())}</h2><div class="tabla"><table>'
                      '<tr><th>#</th><th>Prueba</th><th>Archivo · clase · método</th><th>Estado</th>'
                      '<th class="num">Tiempo</th></tr>')
        for n, r in enumerate(grupo, 1):
            archivo, clase = archivo_y_clase(r['id'])
            metodo = r['id'].rsplit('.', 1)[-1]
            detalle = f'<pre>{e(r["detalle"])}</pre>' if r['detalle'] else ''
            partes.append(
                f'<tr><td class="num">{n}</td>'
                f'<td>{e(r["descripcion"] or nombre_legible(r["id"]))}{detalle}</td>'
                f'<td><code>{e(archivo)}</code><br><code>{e(clase)}.{e(metodo)}</code></td>'
                f'<td class="estado {r["estado"]}">{e(ESTADOS[r["estado"]])}</td>'
                f'<td class="num">{r["segundos"]:.2f} s</td></tr>')
        partes.append('</table></div>')

    # Cobertura
    partes.append('<h2>Cobertura de código</h2>'
                  '<p class="nota">Porcentaje de sentencias del código de la aplicación que se ejecutaron '
                  'durante las pruebas (no incluye el código de las pruebas ni las migraciones). '
                  'Detalle línea por línea en <code>cobertura_html/index.html</code>.</p>'
                  '<div class="tabla"><table><tr><th>Archivo</th><th class="num">Sentencias</th>'
                  '<th class="num">Sin cubrir</th><th class="num">Cobertura</th><th></th>'
                  '<th>Líneas sin cubrir</th></tr>')
    for f in filas_cob:
        nivel = '' if f['porcentaje'] >= 90 else ('media' if f['porcentaje'] >= 70 else 'baja')
        partes.append(
            f'<tr><td><code>{e(f["archivo"])}</code></td><td class="num">{f["sentencias"]}</td>'
            f'<td class="num">{f["faltantes"]}</td><td class="num"><b>{f["porcentaje"]:.0f} %</b></td>'
            f'<td><div class="barra"><i class="{nivel}" style="width:{f["porcentaje"]:.0f}%"></i></div></td>'
            f'<td><code>{e(f["lineas"]) or "—"}</code></td></tr>')
    total_sent = sum(f['sentencias'] for f in filas_cob)
    total_falt = sum(f['faltantes'] for f in filas_cob)
    partes.append(f'<tr><td><b>Total</b></td><td class="num"><b>{total_sent}</b></td>'
                  f'<td class="num"><b>{total_falt}</b></td><td class="num"><b>{total_cob:.0f} %</b></td>'
                  '<td></td><td></td></tr></table></div>')

    # Evidencias funcionales
    capturas = sorted((SALIDA / 'funcionales').glob('CU*.png'))
    if capturas:
        partes.append('<h2>Evidencias de las pruebas funcionales</h2><div class="capturas">')
        for img in capturas:
            datos = base64.b64encode(img.read_bytes()).decode()
            titulo = img.stem.replace('_', ' ').replace('CU0', 'CU-0', 1)
            partes.append(f'<figure><img src="data:image/png;base64,{datos}" alt="{e(titulo)}">'
                          f'<figcaption>{e(titulo)}</figcaption></figure>')
        partes.append('</div>')

    # Entorno
    partes.append('<h2>Entorno de ejecución</h2><div class="tabla"><table>')
    for clave, valor in info:
        partes.append(f'<tr><td><b>{e(clave)}</b></td><td>{e(valor)}</td></tr>')
    partes.append('</table></div></main>')
    return '<!doctype html><html lang="es"><head><meta charset="utf-8">' \
           '<meta name="viewport" content="width=device-width, initial-scale=1">' + '\n'.join(partes) + '</html>'


def main():
    SALIDA.mkdir(exist_ok=True)
    ResultadoRegistrado.registros.clear()
    with open(SALIDA / 'log_pruebas.txt', 'w', encoding='utf-8') as log:
        fallos, segundos = ejecutar_pruebas(log)
        cobertura.stop()
        cobertura.save()

        texto_cobertura = io.StringIO()
        total_cob = cobertura.report(file=texto_cobertura)
        (SALIDA / 'cobertura.txt').write_text(texto_cobertura.getvalue(), encoding='utf-8')
        cobertura.html_report(directory=str(SALIDA / 'cobertura_html'),
                              title='Cobertura de código · EmoVisión')

        log.write('\n' + '=' * 78 + '\nCOBERTURA DE CÓDIGO\n' + texto_cobertura.getvalue())

    registros = ResultadoRegistrado.registros
    filas_cob, info = datos_cobertura(), entorno()
    reporte = generar_html(registros, segundos, filas_cob, total_cob, info)
    (SALIDA / 'reporte_pruebas.html').write_text(reporte, encoding='utf-8')

    # Los mismos datos en JSON, para reutilizarlos (por ejemplo, en el informe).
    resultados = {
        'segundos': segundos, 'cobertura_total': total_cob, 'cobertura': filas_cob,
        'entorno': info,
        'pruebas': [dict(r, tipo=tipo_de(r['id'])) for r in registros],
    }
    (SALIDA / 'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2),
                                            encoding='utf-8')

    print(f'\nPruebas: {len(registros)} · fallidas/errores: {fallos} · cobertura: {total_cob:.0f} %')
    print(f'Reporte:   {SALIDA / "reporte_pruebas.html"}')
    print(f'Log:       {SALIDA / "log_pruebas.txt"}')
    print(f'Cobertura: {SALIDA / "cobertura_html" / "index.html"}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
