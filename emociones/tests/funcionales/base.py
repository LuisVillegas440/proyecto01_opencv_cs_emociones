"""Infraestructura de las pruebas funcionales (navegador real con Playwright).

Cada clase de prueba:
1. Levanta un servidor Django real en un puerto libre (StaticLiveServerTestCase).
2. Genera un video .y4m que el navegador usará como **cámara simulada**
   (a partir de una imagen: con rostro o sin rostro).
3. Abre Microsoft Edge o Google Chrome (o el Chromium de Playwright) sin ventana
   y controla la página como lo haría un usuario: clics, escritura y lectura de la pantalla.
4. Guarda capturas de pantalla como evidencia en `evidencias/funcionales/`.

Variables de entorno opcionales:
- NAVEGADOR_PRUEBAS = msedge | chrome | chromium   (por defecto prueba en ese orden)
- PRUEBAS_VISIBLES  = 1   -> muestra la ventana del navegador (útil para demostraciones)
- EVIDENCIAS_DIR    = carpeta donde guardar las capturas
"""
import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag

from emociones import registro

try:
    from playwright.sync_api import Error as ErrorPlaywright
    from playwright.sync_api import sync_playwright
except ImportError:  # Playwright es una dependencia solo de desarrollo.
    sync_playwright = None

EVIDENCIAS = Path(os.environ.get('EVIDENCIAS_DIR', settings.BASE_DIR / 'evidencias' / 'funcionales'))
#: Navegador usado en la última ejecución (lo lee el generador del reporte de pruebas).
NAVEGADOR_USADO = {}
ANCHO_CAMARA, ALTO_CAMARA = 640, 400
TIEMPO_ESPERA_MS = 20_000


def escribir_video_y4m(ruta, imagen_bgr, cuadros=30):
    """Escribe un video Y4M (formato que Chromium acepta como cámara simulada)."""
    imagen = cv2.resize(imagen_bgr, (ANCHO_CAMARA, ALTO_CAMARA))
    yuv = cv2.cvtColor(imagen, cv2.COLOR_BGR2YUV_I420).tobytes()
    with open(ruta, 'wb') as archivo:
        archivo.write(f'YUV4MPEG2 W{ANCHO_CAMARA} H{ALTO_CAMARA} F30:1 Ip A1:1 C420jpeg\n'.encode())
        for _ in range(cuadros):
            archivo.write(b'FRAME\n' + yuv)


def imagen_sin_rostro():
    return np.full((ALTO_CAMARA, ANCHO_CAMARA, 3), 110, dtype=np.uint8)


@tag('funcional')
@unittest.skipIf(sync_playwright is None,
                 'Playwright no está instalado: pip install -r requirements-dev.txt')
class PruebaFuncional(StaticLiveServerTestCase):
    """Clase base: servidor + navegador con cámara simulada."""

    #: Imagen que verá la cámara simulada. Las subclases la reemplazan.
    imagen_camara = staticmethod(imagen_sin_rostro)

    @classmethod
    def setUpClass(cls):
        # Playwright usa un bucle asyncio; esto permite consultar la base de datos
        # desde la prueba mientras el navegador está abierto.
        cls._async_previo = os.environ.get('DJANGO_ALLOW_ASYNC_UNSAFE')
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        super().setUpClass()

        cls._temporal = tempfile.TemporaryDirectory()
        video = Path(cls._temporal.name) / 'camara.y4m'
        escribir_video_y4m(video, cls.imagen_camara())

        cls._playwright = sync_playwright().start()
        try:
            cls.navegador = cls._abrir_navegador(video)
        except unittest.SkipTest:
            cls._cerrar_recursos()
            super().tearDownClass()
            raise
        EVIDENCIAS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _abrir_navegador(cls, video):
        argumentos = [
            '--use-fake-device-for-media-stream',      # cámara simulada
            '--use-fake-ui-for-media-stream',          # acepta el permiso sin preguntar
            f'--use-file-for-fake-video-capture={video}',
        ]
        visible = os.environ.get('PRUEBAS_VISIBLES') == '1'
        elegido = os.environ.get('NAVEGADOR_PRUEBAS')
        canales = [elegido] if elegido else ['msedge', 'chrome', 'chromium']
        errores = []
        for canal in canales:
            try:
                navegador = cls._playwright.chromium.launch(
                    channel=None if canal == 'chromium' else canal,
                    headless=not visible,
                    slow_mo=300 if visible else 0,
                    args=argumentos,
                )
                NAVEGADOR_USADO.update(nombre=canal, version=navegador.version)
                return navegador
            except ErrorPlaywright as error:
                errores.append(f'{canal}: {str(error).splitlines()[0]}')
        raise unittest.SkipTest('No se encontró un navegador compatible ('
                                + '; '.join(errores)
                                + '). Instale Edge/Chrome o ejecute: playwright install chromium')

    @classmethod
    def _cerrar_recursos(cls):
        if getattr(cls, 'navegador', None):
            cls.navegador.close()
        cls._playwright.stop()
        cls._temporal.cleanup()
        if cls._async_previo is None:
            os.environ.pop('DJANGO_ALLOW_ASYNC_UNSAFE', None)
        else:
            os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = cls._async_previo

    @classmethod
    def tearDownClass(cls):
        cls._cerrar_recursos()
        super().tearDownClass()

    def setUp(self):
        registro._ultimo_guardado.clear()
        self.contexto = self.navegador.new_context(
            viewport={'width': 1366, 'height': 900}, accept_downloads=True, locale='es-EC')
        self.page = self.contexto.new_page()
        self.page.set_default_timeout(TIEMPO_ESPERA_MS)
        # Registrar errores de JavaScript para verificar que la interfaz es estable.
        self.errores_js = []
        self.page.on('pageerror', lambda error: self.errores_js.append(str(error)))
        self.page.on('console', self._registrar_consola)
        self.page.on('response', self._registrar_respuesta)

    def _registrar_consola(self, mensaje):
        # Los fallos de carga se revisan en _registrar_respuesta (con su URL).
        if mensaje.type == 'error' and not mensaje.text.startswith('Failed to load resource'):
            self.errores_js.append(mensaje.text)

    def _registrar_respuesta(self, respuesta):
        # El navegador pide /favicon.ico por su cuenta; el proyecto no define uno.
        if respuesta.status >= 400 and not respuesta.url.endswith('/favicon.ico'):
            self.errores_js.append(f'HTTP {respuesta.status} en {respuesta.url}')

    def tearDown(self):
        self.contexto.close()

    # --- Ayudas para las pruebas -------------------------------------------------
    def abrir(self, ruta='/'):
        self.page.goto(self.live_server_url + ruta)

    def texto(self, selector):
        return self.page.locator(selector).inner_text().strip()

    def esperar(self, expresion_js, descripcion):
        """Espera hasta que la expresión JS sea verdadera; si no, falla con un mensaje claro."""
        try:
            self.page.wait_for_function(expresion_js)
        except ErrorPlaywright:
            self.fail(f'Tiempo agotado esperando: {descripcion}')

    def evidencia(self, nombre):
        """Guarda una captura de la página completa como evidencia de la prueba."""
        self.page.screenshot(path=str(EVIDENCIAS / f'{nombre}.png'), full_page=True)

    def assertSinErroresJS(self):
        self.assertEqual(self.errores_js, [], 'La página registró errores de JavaScript')
