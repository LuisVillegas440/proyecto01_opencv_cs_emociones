"""Pruebas unitarias de los modelos de datos (emociones/models.py)."""
from django.test import TestCase

from emociones.models import RegistroEmocion, SesionAnalisis


class ModelosTests(TestCase):
    def test_emocion_predominante(self):
        """El modelo calcula la emoción más frecuente de una sesión."""
        sesion = SesionAnalisis.objects.create(nombre='x')
        for emocion in ['felicidad', 'felicidad', 'neutral']:
            RegistroEmocion.objects.create(sesion=sesion, rostro_id=1, emocion=emocion,
                                           confianza=0.9, probabilidades={})
        self.assertEqual(sesion.emocion_predominante(), 'felicidad')
        self.assertIsNone(SesionAnalisis.objects.create(nombre='y').emocion_predominante())
