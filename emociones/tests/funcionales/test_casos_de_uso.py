"""Pruebas funcionales: casos de uso clave probados en un navegador real.

CU-01  Inicio: la página principal carga con todos sus controles.
CU-02  Detección en video: al iniciar la cámara se detecta el rostro y se muestra la emoción.
CU-03  Sesión y resultados: al detener se guarda la sesión y se visualizan sus gráficos.
CU-04  Historial y CSV: las sesiones guardadas se listan y se pueden exportar.
CU-05  Sin rostro: sin personas frente a la cámara el sistema sigue estable.
CU-06  Permiso denegado: si el usuario bloquea la cámara se muestra un mensaje claro.
CU-07  Administración: un administrador inicia sesión y consulta las sesiones guardadas.
"""
import csv
import io

import cv2
from django.contrib.auth.models import User

from emociones.models import SesionAnalisis
from emociones.tests.utilidades import IMAGEN_ROSTRO, crear_sesion_con_datos

from .base import PruebaFuncional, imagen_sin_rostro

# Expresiones JavaScript reutilizadas.
JS_CONECTADO = "document.getElementById('estado-conexion').textContent === 'Conectado'"
JS_HAY_ROSTRO = JS_CONECTADO + " && Number(document.getElementById('estado-rostros').textContent) >= 1"
JS_OVERLAY_DIBUJADO = """() => {
    const c = document.getElementById('overlay');
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return true;
    return false;
}"""
JS_SUMA_BARRAS = """() => [...document.querySelectorAll('.barra-emocion .valor')]
    .reduce((total, el) => total + parseInt(el.textContent, 10), 0)"""


def imagen_con_rostro():
    return cv2.imread(str(IMAGEN_ROSTRO))


class CamaraConRostroTests(PruebaFuncional):
    """La cámara simulada muestra una persona."""
    imagen_camara = staticmethod(imagen_con_rostro)

    def iniciar_camara(self, nombre_sesion):
        self.abrir('/')
        self.page.fill('#nombre-sesion', nombre_sesion)
        self.page.click('#btn-iniciar')
        self.esperar(JS_HAY_ROSTRO, 'que se conecte y detecte un rostro')

    def test_cu01_inicio_muestra_interfaz(self):
        """CU-01 Inicio: la página principal carga con sus controles, las 8 emociones y la navegación."""
        self.abrir('/')
        self.assertIn('EmoVisión', self.page.title())
        self.assertTrue(self.page.locator('#btn-iniciar').is_enabled())
        self.assertTrue(self.page.locator('#btn-detener').is_disabled())
        self.assertIn('Iniciar cámara', self.texto('#mensaje'))
        self.assertEqual(self.page.locator('.barra-emocion').count(), 8)
        self.assertTrue(self.page.locator('nav a', has_text='Historial').is_visible())
        self.evidencia('CU01_inicio')
        self.assertSinErroresJS()

    def test_cu02_deteccion_en_video(self):
        """CU-02 Detección en video: se detecta el rostro, se dibuja sobre el video y se muestra la emoción."""
        self.iniciar_camara('Prueba funcional CU-02')

        # Resultado visible sobre el video: el canvas superpuesto tiene dibujos.
        self.esperar(JS_OVERLAY_DIBUJADO, 'que se dibuje el recuadro sobre el video')
        # Tiempo real: el primer análisis carga los modelos; luego debe ir a ≥ 2 análisis/s.
        self.esperar("parseFloat(document.getElementById('estado-fps').textContent) >= 2",
                     'que el análisis alcance al menos 2 FPS')
        # Panel lateral: una emoción reconocida y probabilidades que suman ~100 %.
        emocion = self.texto('#emocion-principal')
        self.assertNotIn(emocion, ('—', 'Sin rostro'))
        self.assertAlmostEqual(self.page.evaluate(JS_SUMA_BARRAS), 100, delta=4)
        self.assertEqual(self.page.locator('.barra-emocion.dominante').count(), 1)
        # Estado del sistema.
        self.assertTrue(self.texto('#estado-ms').endswith('ms'))
        self.assertIn('Prueba funcional CU-02', self.texto('#estado-sesion'))
        self.assertEqual(self.texto('#estado-resolucion'), '640×400')
        self.assertTrue(self.page.locator('#btn-iniciar').is_disabled())

        self.evidencia('CU02_deteccion_en_video')
        self.assertSinErroresJS()

    def test_cu03_sesion_guardada_y_resultados(self):
        """CU-03 Sesión y resultados: al detener se guarda la sesión y se visualizan sus gráficos."""
        nombre = 'Prueba funcional CU-03'
        self.iniciar_camara(nombre)
        self.esperar("Number(document.getElementById('estado-guardados').textContent) >= 2",
                     'que se guarden al menos 2 registros')

        self.page.click('#btn-detener')
        enlace = self.page.locator('#estado-sesion a', has_text='Ver sesión')
        enlace.wait_for()
        self.assertIn('detenida', self.texto('#mensaje').lower())
        self.page.wait_for_load_state('networkidle')  # que termine el último análisis en curso
        enlace.click()

        # Página de detalle con tarjetas y gráficos dibujados por Chart.js.
        self.page.wait_for_url('**/historial/*/')
        self.assertIn(nombre, self.texto('h1'))
        self.assertEqual(self.page.locator('.tarjeta').count(), 5)
        self.esperar("window.Chart && Chart.getChart(document.getElementById('grafico-tiempo'))"
                     " && Chart.getChart(document.getElementById('grafico-distribucion'))",
                     'que se dibujen los gráficos')
        self.page.wait_for_timeout(1500)  # que termine la animación de Chart.js antes de la captura
        self.evidencia('CU03_detalle_de_sesion')

        # La base de datos refleja la sesión cerrada con sus registros.
        sesion = SesionAnalisis.objects.get(nombre=nombre)
        self.assertGreaterEqual(sesion.registros.count(), 2)
        self.page.wait_for_timeout(500)  # margen para que llegue el aviso de cierre (sendBeacon)
        sesion.refresh_from_db()
        self.assertIsNotNone(sesion.fin)
        self.assertSinErroresJS()

    def test_cu04_historial_y_exportar_csv(self):
        """CU-04 Historial y CSV: la sesión aparece en el historial y se exporta a CSV."""
        sesion = crear_sesion_con_datos('Sesión del historial')
        self.abrir('/')
        self.page.click('nav a:has-text("Historial")')
        fila = self.page.locator('tbody tr', has_text='Sesión del historial')
        fila.wait_for()  # espera a que la fila aparezca (falla si no aparece)
        self.assertIn('Felicidad', fila.inner_text())
        self.evidencia('CU04_historial')

        fila.locator('a', has_text='Ver').click()
        self.page.wait_for_url(f'**/historial/{sesion.pk}/')
        self.page.wait_for_timeout(1500)  # que termine la animación de los gráficos
        self.evidencia('CU04_detalle_varias_emociones')
        with self.page.expect_download() as descarga:
            self.page.click('text=Descargar CSV')
        archivo = descarga.value
        self.assertTrue(archivo.suggested_filename.endswith('.csv'))
        with open(archivo.path(), encoding='utf-8-sig') as f:
            filas = list(csv.reader(io.StringIO(f.read())))
        self.assertEqual(filas[0][4], 'emocion')
        self.assertEqual(len(filas), 1 + 14)
        self.assertSinErroresJS()

    def test_cu07_panel_de_administracion(self):
        """CU-07 Administración: un administrador inicia sesión y consulta las sesiones guardadas."""
        User.objects.create_superuser('admin', 'admin@example.com', 'clave-segura-123')
        crear_sesion_con_datos('Sesión para el administrador')
        self.abrir('/admin/')
        self.page.fill('#id_username', 'admin')
        self.page.fill('#id_password', 'clave-segura-123')
        self.page.click('input[type=submit]')
        self.page.click('text=Sesiones de análisis')
        fila = self.page.locator('#result_list tbody tr', has_text='Sesión para el administrador')
        fila.wait_for()  # espera a que la fila aparezca (falla si no aparece)
        self.assertIn('felicidad', fila.inner_text())       # emoción predominante
        self.assertIn('14', fila.inner_text())              # número de registros
        self.evidencia('CU07_panel_administracion')
        self.assertSinErroresJS()


class CamaraSinRostroTests(PruebaFuncional):
    """La cámara simulada muestra una imagen vacía, sin personas."""
    imagen_camara = staticmethod(imagen_sin_rostro)

    def test_cu05_sin_rostro_sistema_estable(self):
        """CU-05 Sin rostro: sin personas frente a la cámara el sistema sigue estable."""
        self.abrir('/')
        self.page.click('#btn-iniciar')
        self.esperar(JS_CONECTADO + " && document.getElementById('estado-rostros').textContent === '0'",
                     'que el sistema se conecte sin detectar rostros')
        self.page.wait_for_timeout(2000)  # dejar correr el análisis unos segundos

        self.assertEqual(self.texto('#emocion-principal'), 'Sin rostro')
        self.assertEqual(self.texto('#estado-conexion'), 'Conectado')
        self.assertEqual(self.texto('#estado-guardados'), '0')
        self.assertEqual(self.page.evaluate(JS_SUMA_BARRAS), 0)
        self.assertFalse(self.page.evaluate(JS_OVERLAY_DIBUJADO))
        self.evidencia('CU05_sin_rostro')
        self.assertSinErroresJS()


class PermisoDenegadoTests(PruebaFuncional):
    """El usuario bloquea el acceso a la cámara."""

    def setUp(self):
        super().setUp()
        # Simula que el usuario pulsa «Bloquear» en el aviso de permisos del navegador.
        self.page.add_init_script("""
            navigator.mediaDevices.getUserMedia = () =>
                Promise.reject(new DOMException('Permiso denegado', 'NotAllowedError'));
        """)

    def test_cu06_permiso_denegado_muestra_mensaje(self):
        """CU-06 Permiso denegado: si se bloquea la cámara se muestra un mensaje claro."""
        self.abrir('/')
        self.page.click('#btn-iniciar')
        self.page.locator('#mensaje', has_text='Permiso de cámara denegado').wait_for()
        self.assertTrue(self.page.locator('#btn-iniciar').is_enabled())
        self.assertTrue(self.page.locator('#btn-detener').is_disabled())
        self.assertEqual(SesionAnalisis.objects.count(), 0)  # no se crea sesión sin cámara
        self.evidencia('CU06_permiso_denegado')
        self.assertSinErroresJS()
