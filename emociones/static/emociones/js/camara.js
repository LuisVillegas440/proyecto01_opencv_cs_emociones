/**
 * Captura de video desde el navegador y envío de frames al servidor.
 *
 * Flujo:
 *   getUserMedia -> <video> -> canvas oculto -> JPEG -> POST /api/analizar/
 *   -> respuesta JSON -> se dibuja sobre el canvas "overlay".
 *
 * Solo hay un request en vuelo a la vez, así el servidor nunca se satura:
 * el siguiente frame se envía cuando llega la respuesta del anterior.
 */
(function () {
  'use strict';

  const INTERVALO_MS = 150;     // pausa mínima entre envíos
  const CALIDAD_JPEG = 0.7;
  const ANCHO_ENVIO = 640;      // se reduce el frame antes de enviarlo

  const video = document.getElementById('video');
  const overlay = document.getElementById('overlay');
  const ctxOverlay = overlay.getContext('2d');
  const mensaje = document.getElementById('mensaje');
  const btnIniciar = document.getElementById('btn-iniciar');
  const btnDetener = document.getElementById('btn-detener');
  const estado = {
    conexion: document.getElementById('estado-conexion'),
    resolucion: document.getElementById('estado-resolucion'),
    rostros: document.getElementById('estado-rostros'),
    ms: document.getElementById('estado-ms'),
    fps: document.getElementById('estado-fps'),
  };

  /** Presentación de cada emoción: viene de emociones/presentacion.py. */
  const EMOCIONES = JSON.parse(document.getElementById('presentacion-emociones').textContent);

  // Id aleatorio de esta pestaña: el servidor lo usa para suavizar resultados.
  const CLIENTE_ID = Math.random().toString(36).slice(2, 12);

  const panelPrincipal = document.getElementById('emocion-principal');
  const contenedorBarras = document.getElementById('barras');
  const barras = {};
  for (const [clave, info] of Object.entries(EMOCIONES)) {
    const fila = document.createElement('div');
    fila.className = 'barra-emocion';
    fila.innerHTML =
      '<span>' + info.emoji + '</span><span>' + info.etiqueta + '</span>' +
      '<div class="pista"><div class="relleno"></div></div><span class="valor">0%</span>';
    fila.querySelector('.relleno').style.background = info.color;
    contenedorBarras.appendChild(fila);
    barras[clave] = {
      fila: fila,
      relleno: fila.querySelector('.relleno'),
      valor: fila.querySelector('.valor'),
    };
  }

  const lienzoEnvio = document.createElement('canvas');
  const ctxEnvio = lienzoEnvio.getContext('2d');

  let stream = null;
  let activo = false;
  let tiemposRespuesta = [];
  let sesionId = null;       // SesionAnalisis en curso (null = no se guarda)
  let totalGuardados = 0;

  const inputNombre = document.getElementById('nombre-sesion');
  const estadoSesion = document.getElementById('estado-sesion');
  const estadoGuardados = document.getElementById('estado-guardados');

  function csrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function mostrarMensaje(texto) {
    mensaje.textContent = texto;
    mensaje.hidden = !texto;
  }

  function ponerEstado(el, texto, clase) {
    el.textContent = texto;
    el.className = clase || '';
  }

  /** Crea una SesionAnalisis en el servidor. Si falla, se analiza sin guardar. */
  async function crearSesion() {
    const datos = new FormData();
    datos.append('nombre', inputNombre.value.trim());
    try {
      const resp = await fetch(window.URL_INICIAR_SESION, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body: datos,
      });
      const json = await resp.json();
      if (!resp.ok || !json.ok) throw new Error(json.error || 'HTTP ' + resp.status);
      sesionId = json.sesion;
      totalGuardados = 0;
      ponerEstado(estadoSesion, '#' + json.sesion + ' ' + json.nombre, 'ok');
      estadoGuardados.textContent = '0';
    } catch (err) {
      sesionId = null;
      ponerEstado(estadoSesion, 'Sin guardar', 'error');
      console.error('No se pudo crear la sesión:', err);
    }
  }

  /**
   * Cierra la sesión en el servidor. Usa sendBeacon para que funcione
   * incluso al cerrar la pestaña.
   */
  function cerrarSesion() {
    if (sesionId === null) return;
    const datos = new FormData();
    datos.append('csrfmiddlewaretoken', csrfToken());
    navigator.sendBeacon(window.URL_FINALIZAR_SESION.replace('/0/', '/' + sesionId + '/'), datos);
    // Enlace al detalle de la sesión recién terminada.
    const enlace = document.createElement('a');
    enlace.href = window.URL_DETALLE_SESION.replace('/0/', '/' + sesionId + '/');
    enlace.textContent = 'Ver sesión #' + sesionId + ' →';
    estadoSesion.className = '';
    estadoSesion.replaceChildren(enlace);
    sesionId = null;
  }

  async function iniciar() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      mostrarMensaje('Este navegador no permite acceder a la cámara.');
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
    } catch (err) {
      const motivo = err.name === 'NotAllowedError'
        ? 'Permiso de cámara denegado. Habilítalo en el navegador.'
        : err.name === 'NotFoundError'
          ? 'No se encontró ninguna cámara conectada.'
          : 'No se pudo abrir la cámara: ' + err.message;
      mostrarMensaje(motivo);
      return;
    }

    video.srcObject = stream;
    await video.play();

    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    const escala = Math.min(1, ANCHO_ENVIO / video.videoWidth);
    lienzoEnvio.width = Math.round(video.videoWidth * escala);
    lienzoEnvio.height = Math.round(video.videoHeight * escala);

    estado.resolucion.textContent = video.videoWidth + '×' + video.videoHeight;
    mostrarMensaje('');
    btnIniciar.disabled = true;
    btnDetener.disabled = false;
    inputNombre.disabled = true;
    await crearSesion();
    if (!stream) { cerrarSesion(); return; }  // se pulsó «Detener» mientras se creaba
    activo = true;
    tiemposRespuesta = [];
    bucle();
  }

  function detener() {
    activo = false;
    cerrarSesion();
    inputNombre.disabled = false;
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    video.srcObject = null;
    ctxOverlay.clearRect(0, 0, overlay.width, overlay.height);
    btnIniciar.disabled = false;
    btnDetener.disabled = true;
    ponerEstado(estado.conexion, 'Detenido');
    mostrarMensaje('Cámara detenida.');
  }

  function capturarFrame() {
    ctxEnvio.drawImage(video, 0, 0, lienzoEnvio.width, lienzoEnvio.height);
    return new Promise((resolve) => lienzoEnvio.toBlob(resolve, 'image/jpeg', CALIDAD_JPEG));
  }

  async function enviarFrame(blob) {
    const datos = new FormData();
    datos.append('frame', blob, 'frame.jpg');
    datos.append('cliente', CLIENTE_ID);
    if (sesionId !== null) datos.append('sesion', sesionId);
    const resp = await fetch(window.URL_ANALIZAR, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
      body: datos,
    });
    const json = await resp.json();
    if (!resp.ok || !json.ok) throw new Error(json.error || 'HTTP ' + resp.status);
    return json;
  }

  function actualizarFps() {
    const ahora = performance.now();
    tiemposRespuesta.push(ahora);
    tiemposRespuesta = tiemposRespuesta.filter((t) => ahora - t < 2000);
    estado.fps.textContent = (tiemposRespuesta.length / 2).toFixed(1);
  }

  /**
   * Dibuja cajas y etiquetas. Las cajas vienen en coordenadas del frame
   * enviado; se escalan al tamaño del video y se reflejan horizontalmente
   * para coincidir con el video en modo espejo.
   */
  function dibujar(resultado) {
    ctxOverlay.clearRect(0, 0, overlay.width, overlay.height);
    const fx = overlay.width / resultado.ancho;
    const fy = overlay.height / resultado.alto;
    const grosor = Math.max(2, overlay.width / 320);
    const fuente = Math.round(Math.max(14, overlay.width / 40));
    ctxOverlay.font = '600 ' + fuente + 'px system-ui, sans-serif';
    ctxOverlay.textBaseline = 'bottom';

    for (const rostro of resultado.rostros) {
      const [x, y, w, h] = rostro.caja;
      const info = EMOCIONES[rostro.emocion] || EMOCIONES.neutral;
      const bx = overlay.width - (x + w) * fx;  // reflejo horizontal
      const by = y * fy;
      const bw = w * fx;
      const bh = h * fy;

      ctxOverlay.lineWidth = grosor;
      ctxOverlay.strokeStyle = info.color;
      ctxOverlay.strokeRect(bx, by, bw, bh);

      const texto = info.emoji + ' ' + info.etiqueta + ' ' + Math.round(rostro.confianza * 100) + '%';
      const anchoTexto = ctxOverlay.measureText(texto).width + 12;
      const altoTexto = fuente + 10;
      const ty = by - altoTexto < 0 ? by + bh + altoTexto : by;  // debajo si no cabe arriba
      ctxOverlay.fillStyle = info.color;
      ctxOverlay.fillRect(bx - grosor / 2, ty - altoTexto, anchoTexto, altoTexto);
      ctxOverlay.fillStyle = '#0f172a';
      ctxOverlay.fillText(texto, bx + 6 - grosor / 2, ty - 4);
    }
  }

  /** Actualiza el panel lateral con el rostro principal (el más grande). */
  function actualizarPanel(resultado) {
    const principal = resultado.rostros[0];
    for (const [clave, barra] of Object.entries(barras)) {
      const p = principal ? principal.probabilidades[clave] || 0 : 0;
      barra.relleno.style.width = (p * 100).toFixed(1) + '%';
      barra.valor.textContent = Math.round(p * 100) + '%';
      barra.fila.classList.toggle('dominante', !!principal && principal.emocion === clave);
    }
    if (principal) {
      const info = EMOCIONES[principal.emocion] || EMOCIONES.neutral;
      panelPrincipal.textContent = info.emoji + ' ' + info.etiqueta;
      panelPrincipal.style.color = info.color;
    } else {
      panelPrincipal.textContent = 'Sin rostro';
      panelPrincipal.style.color = '';
    }
  }

  async function bucle() {
    while (activo) {
      const inicio = performance.now();
      try {
        const blob = await capturarFrame();
        const resultado = await enviarFrame(blob);
        if (!activo) break;
        dibujar(resultado);
        actualizarPanel(resultado);
        ponerEstado(estado.conexion, 'Conectado', 'ok');
        estado.rostros.textContent = resultado.rostros.length;
        estado.ms.textContent = resultado.ms + ' ms';
        actualizarFps();
        if (resultado.guardados) {
          totalGuardados += resultado.guardados;
          estadoGuardados.textContent = totalGuardados;
        }
      } catch (err) {
        ponerEstado(estado.conexion, 'Error', 'error');
        console.error('Error analizando frame:', err);
        await new Promise((r) => setTimeout(r, 1000)); // reintento suave
      }
      const espera = INTERVALO_MS - (performance.now() - inicio);
      if (espera > 0) await new Promise((r) => setTimeout(r, espera));
    }
  }

  btnIniciar.addEventListener('click', iniciar);
  btnDetener.addEventListener('click', detener);
  window.addEventListener('beforeunload', detener);
})();
