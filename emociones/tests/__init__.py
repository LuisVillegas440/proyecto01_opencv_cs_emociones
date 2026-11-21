"""Pruebas automáticas de la app «emociones».

Organización:
- unitarias/   : prueban una función o clase de forma aislada
                 (módulo de visión con OpenCV, seguimiento, estadísticas, modelos).
- integracion/ : prueban varias capas juntas a través de las rutas de Django
                 (URL -> vista -> OpenCV / base de datos -> respuesta).
- funcionales/ : prueban casos de uso completos en un navegador real (Edge/Chrome)
                 con una cámara simulada, como lo haría un usuario. Requieren
                 `pip install -r requirements-dev.txt`; si falta Playwright se omiten.
- utilidades.py: datos y archivos de prueba compartidos.

Ejecutar todo:            python manage.py test emociones
Solo unitarias:           python manage.py test emociones.tests.unitarias
Solo integración:         python manage.py test emociones.tests.integracion
Solo funcionales:         python manage.py test emociones.tests.funcionales
"""
