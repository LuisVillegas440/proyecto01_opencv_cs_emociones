# EmoVisión: detección de emociones en tiempo real

Aplicación web en **Django** que captura video de la cámara desde el navegador, lo procesa con **OpenCV** para **detectar rostros** y **reconocer la emoción** de cada uno, y muestra los resultados en vivo sobre el video. Cada sesión de análisis se guarda en la base de datos y se puede revisar luego en un historial con estadísticas, gráficos y exportación a CSV.

<!-- Agregar capturas en docs/capturas/ y descomentar:
![Cámara en vivo](docs/capturas/camara.png)
![Detalle de una sesión](docs/capturas/detalle.png)
-->

---

## Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Cámara en vivo** | Captura video con la cámara del navegador y envía frames al servidor unas 6 veces por segundo |
| **Detección de rostros** | Localiza todos los rostros del frame con la red neuronal **YuNet** (`cv2.FaceDetectorYN`) |
| **Reconocimiento de emociones** | Clasifica cada rostro en 8 emociones con el modelo **FER+** cargado con `cv2.dnn`: neutral, felicidad, sorpresa, tristeza, enojo, disgusto, miedo y desprecio |
| **Procesamiento** | Mejora el contraste del rostro con CLAHE, sigue cada rostro entre frames (IoU) y suaviza los resultados (media móvil exponencial) para que la etiqueta no parpadee |
| **Resultados sobre el video** | Caja de color por emoción, con emoji y porcentaje de confianza, y barras de probabilidad en vivo |
| **Sesiones** | Cada vez que se inicia la cámara se crea una sesión con nombre; se guarda una muestra por rostro por segundo |
| **Historial y estadísticas** | Emoción predominante, duración, rostros, índice de ánimo, gráfico en el tiempo, distribución y resumen por rostro |
| **Exportar CSV** | Descarga todos los registros de una sesión con las 8 probabilidades |
| **Panel de administración** | Consulta y filtra sesiones y registros desde `/admin` |

> **Privacidad:** no se guarda ninguna imagen ni foto de rostros. Solo se almacenan los resultados numéricos del análisis.

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Lenguaje backend | Python 3.14 |
| Framework web | Django 6.1 |
| Visión por computadora | OpenCV 5.0 (`opencv-python`) y NumPy |
| Detector de rostros | YuNet, de OpenCV Zoo (ONNX, ~230 KB) |
| Clasificador de emociones | FER+, de ONNX Model Zoo (ONNX, ~34 MB) |
| Base de datos | SQLite |
| Frontend | HTML, CSS y JavaScript; Chart.js 4.4.1 incluido localmente, sin depender de internet |

No se usa TensorFlow ni PyTorch: toda la inferencia se ejecuta con el módulo `dnn` de OpenCV.

---

## Instalación y ejecución

### Requisitos previos
- Python 3.12 o superior (probado con 3.14)
- Git
- Una cámara web y un navegador moderno (Chrome, Edge o Firefox)

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/LuisVillegas440/proyecto01_opencv_cs_emociones.git
cd proyecto01_opencv_cs_emociones

# 2. Crear y activar el entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear la base de datos
python manage.py migrate

# 5. (Opcional) Crear un usuario para el panel de administración
python manage.py createsuperuser

# 6. Iniciar el servidor
python manage.py runserver
```

Abrir **http://127.0.0.1:8000/** y presionar **«Iniciar cámara»**. El navegador pedirá permiso para usar la cámara.

> Los modelos `.onnx` ya vienen en la carpeta `modelos_ml/`; no hay que descargar nada más.
> La cámara solo funciona en `localhost`/`127.0.0.1` o con HTTPS, por una restricción de seguridad de los navegadores.

### Páginas

| URL | Descripción |
|---|---|
| `/` | Cámara en vivo con detección |
| `/historial/` | Lista de sesiones guardadas |
| `/historial/<id>/` | Estadísticas y gráficos de una sesión |
| `/historial/<id>/csv/` | Descarga del CSV de la sesión |
| `/admin/` | Panel de administración de Django |

---

## Cómo funciona

```mermaid
flowchart LR
    A[Cámara del navegador<br/>getUserMedia] -->|frame JPEG 640 px<br/>cada ~150 ms| B[POST /api/analizar/]
    B --> C[Decodificar<br/>cv2.imdecode]
    C --> D[Detectar rostros<br/>YuNet]
    D --> E[Recortar + gris + CLAHE<br/>64×64]
    E --> F[Clasificar emoción<br/>FER+ · cv2.dnn]
    F --> G[Seguimiento + suavizado<br/>IoU + EMA]
    G -->|JSON| H[Dibujar cajas y etiquetas<br/>en canvas]
    G -->|1 muestra/seg| I[(SQLite<br/>RegistroEmocion)]
    I --> J[Historial, gráficos y CSV]
```

1. **Captura:** el navegador obtiene el video con `getUserMedia`, reduce cada frame a 640 px de ancho, lo comprime a JPEG y lo envía al servidor. Solo hay una petición en curso a la vez, así el servidor nunca se satura.
2. **Detección:** YuNet devuelve la caja de cada rostro y su confianza. Se descartan rostros menores a 24 px.
3. **Preprocesado:** cada rostro se recorta con un 10 % de margen, se pasa a escala de grises, se redimensiona a 64×64 y se le aplica **CLAHE** (ecualización adaptativa del histograma) para compensar la poca luz.
4. **Reconocimiento:** FER+ procesa todos los rostros del frame en una sola pasada y devuelve 8 puntuaciones, que se convierten en probabilidades con *softmax*.
5. **Seguimiento y suavizado:** cada rostro se asocia con el del frame anterior por solapamiento (IoU) y conserva un **id estable**. Sus probabilidades se promedian con una **media móvil exponencial**, lo que evita que la etiqueta cambie a cada instante.
6. **Visualización:** la API responde en JSON y el navegador dibuja las cajas sobre el video en modo espejo, además de las barras de probabilidad.
7. **Persistencia:** si hay una sesión activa, se guarda como máximo una muestra por segundo para no llenar la base de datos.

**Rendimiento medido:** unos 43 ms por frame (detección y clasificación) a 640×480 en CPU.

---

## Estructura del proyecto

```
proyecto01_opencv_cs_emociones/
├── config/                     # Configuración del proyecto Django
│   ├── settings.py             #   rutas a los modelos y umbral de detección al final
│   └── urls.py
├── emociones/                  # Aplicación principal
│   ├── vision/                 # Módulo de OpenCV, independiente de Django (reutilizable)
│   │   ├── detector_rostros.py #   YuNet: frame → lista de rostros
│   │   ├── clasificador.py     #   FER+: recorte → probabilidades de 8 emociones
│   │   ├── seguimiento.py      #   asociación entre frames (IoU) y suavizado (EMA)
│   │   └── pipeline.py         #   orquesta todo y es seguro con varios hilos
│   ├── models.py               # SesionAnalisis, RegistroEmocion
│   ├── views.py                # Páginas y API
│   ├── servicios.py            # Carga única de los modelos
│   ├── registro.py             # Guardado limitado a 1 muestra/segundo
│   ├── estadisticas.py         # Cálculos del historial (funciones puras)
│   ├── presentacion.py         # Etiqueta, emoji y color de cada emoción
│   ├── admin.py                # Panel de administración
│   ├── templates/emociones/    # base, camara, historial, sesion_detalle
│   ├── static/emociones/       # css, js (camara.js, sesion.js) y Chart.js
│   └── tests/                  # Pruebas automáticas
├── modelos_ml/                 # Modelos ONNX (YuNet y FER+)
├── manage.py
├── requirements.txt
└── README.md
```

### Modelo de datos

| Tabla | Campos | Descripción |
|---|---|---|
| `SesionAnalisis` | nombre, descripción, inicio, fin | Un período de análisis, desde «Iniciar» hasta «Detener» |
| `RegistroEmocion` | sesión, momento, rostro_id, emoción, confianza, probabilidades (JSON) | Una muestra de un rostro, como máximo una por segundo |

---

## Pruebas

### Pruebas automáticas

```bash
python manage.py test emociones
```

Son 35 pruebas que cubren:
- **Visión** (`test_vision.py`): detección en una imagen con rostro y sin rostro, que las probabilidades sumen 1, el pipeline completo y el seguimiento (id estable, suavizado y descarte de rostros perdidos).
- **API** (`test_api.py`): peticiones sin frame, con imagen inválida, con método incorrecto y con un frame válido.
- **Sesiones** (`test_sesiones.py`): iniciar y finalizar sesiones, el límite de 1 muestra/segundo, que no se guarde nada en sesiones cerradas, y el panel de admin.
- **Historial** (`test_historial.py`): estadísticas, línea de tiempo, páginas y exportación CSV.

### Pruebas manuales

Casos para comprobar el comportamiento con la cámara real:

| # | Caso | Resultado esperado |
|---|---|---|
| 1 | Buena iluminación, 1 persona | Detecta el rostro y la emoción cambia con los gestos |
| 2 | Poca luz o luz lateral | Sigue detectando, quizá con menor confianza |
| 3 | 2–3 personas | Una caja por persona, cada una con su emoción |
| 4 | Nadie frente a la cámara | Panel en «Sin rostro», sin errores |
| 5 | Rostro de perfil o cubierto | No se cae; puede perder el rostro un momento |
| 6 | Permiso de cámara denegado | Mensaje claro en pantalla |
| 7 | Detener e iniciar de nuevo | Se crea una sesión nueva |
| 8 | Cerrar la pestaña sin detener | La sesión queda finalizada en el historial |
| 9 | Exportar CSV y abrirlo en Excel | Se ven bien las tildes y las columnas |

---

## Limitaciones conocidas

- FER+ funciona mejor con **rostros frontales** y buena luz. Las emociones *desprecio* y *disgusto* se detectan con menos frecuencia porque había pocos ejemplos de ellas en el conjunto de entrenamiento.
- El seguimiento entre frames es simple (por solapamiento). Si una persona sale de cuadro y vuelve, recibe un id nuevo.
- La aplicación está pensada para ejecutarse **localmente** con el servidor de desarrollo de Django.
- Se usa **SQLite** por simplicidad. Para usar PostgreSQL solo hay que cambiar `DATABASES` en `config/settings.py` e instalar `psycopg`.

---

## Créditos

- **YuNet**: detector de rostros de [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet).
- **FER+ (emotion-ferplus-8)**: modelo de [ONNX Model Zoo](https://github.com/onnx/models/tree/main/validated/vision/body_analysis/emotion_ferplus), entrenado con el conjunto FER+ de Microsoft.
- **Chart.js**: [chartjs.org](https://www.chartjs.org/).
- Imagen de prueba (`emociones/tests/imagenes/con_rostro.jpg`): muestra `messi5.jpg` de los [ejemplos de OpenCV](https://github.com/opencv/opencv/tree/4.x/samples/data).

Las licencias de cada modelo y librería se pueden consultar en sus repositorios originales.
