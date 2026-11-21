"""Pruebas unitarias de los cálculos del historial (emociones/estadisticas.py)."""
from datetime import timedelta

from django.test import TestCase

from emociones import estadisticas
from emociones.models import RegistroEmocion, SesionAnalisis
from emociones.tests.utilidades import crear_sesion_con_datos


class EstadisticasTests(TestCase):
    def test_calculo_completo(self):
        """Cálculo de emoción predominante, rostros, duración, índice de ánimo y resumen por rostro."""
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
        """La línea de tiempo reparte las emociones por segundo y cada intervalo suma 100 %."""
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
        """En una sesión de 1 hora el gráfico no supera el máximo de puntos."""
        sesion = SesionAnalisis.objects.create(nombre='larga')
        RegistroEmocion.objects.bulk_create([
            RegistroEmocion(sesion=sesion, momento=sesion.inicio + timedelta(seconds=s),
                            rostro_id=1, emocion='neutral', confianza=0.9, probabilidades={})
            for s in range(0, 3600, 5)
        ])
        linea = estadisticas.linea_de_tiempo(list(sesion.registros.all()), sesion.inicio)
        self.assertLessEqual(len(linea['etiquetas']), estadisticas.PUNTOS_MAXIMOS_GRAFICO)

    def test_sesion_vacia(self):
        """Una sesión sin registros produce estadísticas vacías sin errores."""
        sesion = SesionAnalisis.objects.create(nombre='vacía')
        est = estadisticas.calcular(sesion, [])
        self.assertEqual(est['total'], 0)
        self.assertIsNone(est['predominante'])
