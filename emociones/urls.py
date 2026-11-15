"""Rutas de la app de detección de emociones."""
from django.urls import path

from . import views

app_name = 'emociones'

urlpatterns = [
    path('', views.camara, name='camara'),
    path('camara/', views.camara, name='camara_alias'),
    path('historial/', views.historial, name='historial'),
    path('historial/<int:pk>/', views.detalle_sesion, name='detalle_sesion'),
    path('historial/<int:pk>/csv/', views.exportar_csv, name='exportar_csv'),
    path('api/analizar/', views.analizar, name='analizar'),
    path('api/sesiones/iniciar/', views.iniciar_sesion, name='iniciar_sesion'),
    path('api/sesiones/<int:pk>/finalizar/', views.finalizar_sesion, name='finalizar_sesion'),
]
