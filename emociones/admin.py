"""Panel de administración para sesiones y registros de emociones."""
from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import RegistroEmocion, SesionAnalisis


@admin.register(SesionAnalisis)
class SesionAnalisisAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'inicio', 'fin', 'duracion_texto', 'total_registros',
                    'emocion_predominante', 'ver_registros')
    search_fields = ('nombre', 'descripcion')
    date_hierarchy = 'inicio'
    readonly_fields = ('duracion_texto', 'total_registros', 'emocion_predominante', 'ver_registros')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total=Count('registros'))

    @admin.display(description='Duración')
    def duracion_texto(self, obj):
        segundos = int(obj.duracion.total_seconds())
        texto = f'{segundos // 3600:02d}:{segundos % 3600 // 60:02d}:{segundos % 60:02d}'
        return f'{texto} (en curso)' if obj.en_curso else texto

    @admin.display(description='Registros', ordering='_total')
    def total_registros(self, obj):
        return obj._total

    @admin.display(description='Emoción predominante')
    def emocion_predominante(self, obj):
        return obj.emocion_predominante() or '—'

    @admin.display(description='Detalle')
    def ver_registros(self, obj):
        url = reverse('admin:emociones_registroemocion_changelist') + f'?sesion__id__exact={obj.pk}'
        return format_html('<a href="{}">Ver registros</a>', url)


@admin.register(RegistroEmocion)
class RegistroEmocionAdmin(admin.ModelAdmin):
    list_display = ('momento', 'sesion', 'rostro_id', 'emocion', 'confianza_pct')
    list_filter = ('emocion', 'sesion')
    list_select_related = ('sesion',)
    date_hierarchy = 'momento'
    readonly_fields = ('sesion', 'momento', 'rostro_id', 'emocion', 'confianza', 'probabilidades')

    @admin.display(description='Confianza', ordering='confianza')
    def confianza_pct(self, obj):
        return f'{obj.confianza:.0%}'

    def has_add_permission(self, request):
        return False  # los registros solo los crea el análisis en vivo
