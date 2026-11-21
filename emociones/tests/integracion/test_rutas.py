"""Pruebas de integración de las rutas principales: cada URL carga su página."""
from django.test import TestCase
from django.urls import reverse

from emociones.models import SesionAnalisis
from emociones.tests.utilidades import crear_sesion_con_datos


class PaginaCamaraTests(TestCase):
    def test_pagina_carga(self):
        """La página de cámara (/) responde 200 y contiene el reproductor de video."""
        resp = self.client.get(reverse('emociones:camara'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="video"')


class PaginasHistorialTests(TestCase):
    def test_historial_vacio(self):
        """El historial sin sesiones muestra el mensaje de lista vacía."""
        resp = self.client.get(reverse('emociones:historial'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Todavía no hay sesiones')

    def test_historial_lista_sesiones(self):
        """El historial lista las sesiones con su emoción predominante."""
        crear_sesion_con_datos('Sesión A')
        SesionAnalisis.objects.create(nombre='Sesión B')
        resp = self.client.get(reverse('emociones:historial'))
        self.assertContains(resp, 'Sesión A')
        self.assertContains(resp, 'Sesión B')
        self.assertContains(resp, 'Felicidad')

    def test_detalle_con_datos(self):
        """El detalle de una sesión con datos incluye los gráficos y el botón de CSV."""
        sesion = crear_sesion_con_datos()
        resp = self.client.get(reverse('emociones:detalle_sesion', args=[sesion.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="grafico-tiempo"')
        self.assertContains(resp, 'id="datos-grafico"')
        self.assertContains(resp, 'Descargar CSV')

    def test_detalle_sin_registros(self):
        """El detalle de una sesión sin registros muestra un aviso y no carga gráficos."""
        sesion = SesionAnalisis.objects.create(nombre='Sin datos')
        resp = self.client.get(reverse('emociones:detalle_sesion', args=[sesion.pk]))
        self.assertContains(resp, 'no tiene registros')
        self.assertNotContains(resp, 'chart.umd.min.js')

    def test_detalle_inexistente_404(self):
        """Una sesión inexistente responde 404."""
        resp = self.client.get(reverse('emociones:detalle_sesion', args=[9999]))
        self.assertEqual(resp.status_code, 404)
