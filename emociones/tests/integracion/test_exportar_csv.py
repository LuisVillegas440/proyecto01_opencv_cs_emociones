"""Pruebas de integración de la exportación de una sesión a CSV."""
import csv
import io

from django.test import TestCase
from django.urls import reverse

from emociones.tests.utilidades import crear_sesion_con_datos


class ExportarCsvTests(TestCase):
    def test_csv(self):
        """El CSV de una sesión tiene el nombre, las columnas y las filas correctas."""
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
