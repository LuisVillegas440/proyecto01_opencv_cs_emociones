"""Pruebas del historial, el detalle de sesión, el CSV y las estadísticas."""
import csv
import io
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from emociones import estadisticas
from emociones.models import RegistroEmocion, SesionAnalisis


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


class EstadisticasTests(TestCase):
    def test_calculo_completo(self):
        sesion = crear_sesion_con_datos()
        est = estadisticas.calcular(sesion, sesion.registros.order_by('momento'))
        self.assertEqual(est['total'], 14)
        self.assertEqual(est['predominante'], 'felicidad')         # 6 de 14
        self.assertEqual(est['rostros_distintos'], 2)
        self.assertEqual(est['rostros_max'], 2)
        self.assertEqual(est['duracion'], '00:10')
        self.assertEqual(est['animo'], {'positivo': 42.9, 'neutro': 28.6, 'negativo': 28.6})
        por_rostro = {r['rostro_id']: r for r in est['por_rostro']}
        self.assertEqual(por_rostro[1]['emocion'], 'felicidad')
        self.assertEqual(por_rostro[2]['emocion'], 'neutral')

    def test_linea_de_tiempo(self):
        sesion = crear_sesion_con_datos()
        linea = estadisticas.linea_de_tiempo(list(sesion.registros.all()), sesion.inicio)
        self.assertEqual(linea['intervalo_s'], 1)
        self.assertEqual(len(linea['etiquetas']), 10)
        self.assertEqual(linea['series']['felicidad'][0], 50.0)    # 1 feliz + 1 neutral
        self.assertEqual(linea['series']['tristeza'][9], 100.0)
        # En cada intervalo con datos, los porcentajes suman 100.
        for i in range(10):
            self.assertAlmostEqual(sum(linea['series'][e][i] for e in linea['series']), 100.0)

    def test_linea_de_tiempo_sesion_larga_limita_puntos(self):
        sesion = SesionAnalisis.objects.create(nombre='larga')
        RegistroEmocion.objects.bulk_create([
            RegistroEmocion(sesion=sesion, momento=sesion.inicio + timedelta(seconds=s),
                            rostro_id=1, emocion='neutral', confianza=0.9, probabilidades={})
            for s in range(0, 3600, 5)
        ])
        linea = estadisticas.linea_de_tiempo(list(sesion.registros.all()), sesion.inicio)
        self.assertLessEqual(len(linea['etiquetas']), estadisticas.PUNTOS_MAXIMOS_GRAFICO)

    def test_sesion_vacia(self):
        sesion = SesionAnalisis.objects.create(nombre='vacía')
        est = estadisticas.calcular(sesion, [])
        self.assertEqual(est['total'], 0)
        self.assertIsNone(est['predominante'])


class PaginasHistorialTests(TestCase):
    def test_historial_vacio(self):
        resp = self.client.get(reverse('emociones:historial'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Todavía no hay sesiones')

    def test_historial_lista_sesiones(self):
        crear_sesion_con_datos('Sesión A')
        SesionAnalisis.objects.create(nombre='Sesión B')
        resp = self.client.get(reverse('emociones:historial'))
        self.assertContains(resp, 'Sesión A')
        self.assertContains(resp, 'Sesión B')
        self.assertContains(resp, 'Felicidad')

    def test_detalle_con_datos(self):
        sesion = crear_sesion_con_datos()
        resp = self.client.get(reverse('emociones:detalle_sesion', args=[sesion.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="grafico-tiempo"')
        self.assertContains(resp, 'id="datos-grafico"')
        self.assertContains(resp, 'Descargar CSV')

    def test_detalle_sin_registros(self):
        sesion = SesionAnalisis.objects.create(nombre='Sin datos')
        resp = self.client.get(reverse('emociones:detalle_sesion', args=[sesion.pk]))
        self.assertContains(resp, 'no tiene registros')
        self.assertNotContains(resp, 'chart.umd.min.js')

    def test_detalle_inexistente_404(self):
        resp = self.client.get(reverse('emociones:detalle_sesion', args=[9999]))
        self.assertEqual(resp.status_code, 404)


class ExportarCsvTests(TestCase):
    def test_csv(self):
        sesion = crear_sesion_con_datos('Clase de Construcción')
        resp = self.client.get(reverse('emociones:exportar_csv', args=[sesion.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(f'sesion_{sesion.pk}_clase-de-construccion.csv', resp['Content-Disposition'])

        contenido = resp.content.decode('utf-8-sig')
        filas = list(csv.reader(io.StringIO(contenido)))
        encabezado, datos = filas[0], filas[1:]
        self.assertEqual(encabezado[:6], ['sesion', 'momento', 'segundos_desde_inicio',
                                          'rostro_id', 'emocion', 'confianza'])
        self.assertEqual(len(encabezado), 6 + 8)
        self.assertEqual(len(datos), 14)
        self.assertEqual(datos[0][0], 'Clase de Construcción')
