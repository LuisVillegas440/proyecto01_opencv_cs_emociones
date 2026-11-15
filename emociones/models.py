"""Modelos de la app: sesiones de análisis y registros de emociones.

No se guardan imágenes de rostros (datos biométricos), solo los resultados.
"""
from django.db import models
from django.db.models import Count
from django.utils import timezone

from .vision import EMOCIONES

OPCIONES_EMOCION = [(e, e.capitalize()) for e in EMOCIONES]


class SesionAnalisis(models.Model):
    """Un período de análisis: desde que se inicia la cámara hasta que se detiene."""
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    inicio = models.DateTimeField(default=timezone.now)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-inicio']
        verbose_name = 'sesión de análisis'
        verbose_name_plural = 'sesiones de análisis'

    def __str__(self):
        return f'{self.nombre} ({timezone.localtime(self.inicio):%d/%m/%Y %H:%M})'

    @property
    def en_curso(self):
        return self.fin is None

    @property
    def duracion(self):
        """Duración como timedelta (hasta ahora si sigue en curso)."""
        return (self.fin or timezone.now()) - self.inicio

    def emocion_predominante(self):
        """Emoción más frecuente entre los registros, o None si no hay."""
        fila = (self.registros.values('emocion')
                .annotate(total=Count('id')).order_by('-total').first())
        return fila['emocion'] if fila else None

    def finalizar(self):
        if self.fin is None:
            self.fin = timezone.now()
            self.save(update_fields=['fin'])


class RegistroEmocion(models.Model):
    """Una muestra de la emoción de un rostro (como máximo una por segundo)."""
    sesion = models.ForeignKey(SesionAnalisis, on_delete=models.CASCADE, related_name='registros')
    momento = models.DateTimeField(default=timezone.now, db_index=True)
    rostro_id = models.PositiveIntegerField(help_text='Id del rostro dentro de la sesión (seguimiento).')
    emocion = models.CharField(max_length=20, choices=OPCIONES_EMOCION)
    confianza = models.FloatField()
    probabilidades = models.JSONField(help_text='Probabilidad de cada una de las 8 emociones.')

    class Meta:
        ordering = ['-momento']
        verbose_name = 'registro de emoción'
        verbose_name_plural = 'registros de emociones'

    def __str__(self):
        return f'Rostro {self.rostro_id}: {self.emocion} ({self.confianza:.0%})'
