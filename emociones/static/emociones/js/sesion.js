/**
 * Gráficos del detalle de una sesión (Chart.js, incluido localmente).
 * Los datos llegan desde Django en el <script id="datos-grafico">.
 */
(function () {
  'use strict';

  if (typeof Chart === 'undefined') {
    console.error('Chart.js no se cargó.');
    return;
  }

  const datos = JSON.parse(document.getElementById('datos-grafico').textContent);
  const emociones = datos.emociones;
  const linea = datos.linea_tiempo;

  Chart.defaults.color = '#5b6b7b';
  Chart.defaults.borderColor = 'rgba(19, 51, 76, 0.1)';
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

  const nombre = (e) => e.emoji + ' ' + e.etiqueta;

  /*
   * Barras apiladas: una barra por intervalo de tiempo, dividida según el
   * porcentaje de muestras de cada emoción (siempre suma 100 %).
   * Los intervalos sin ninguna muestra (no se detectó rostro) se muestran
   * como una barra gris clara "Sin rostro", en vez de un hueco sin explicación.
   */
  const COLOR_SIN_ROSTRO = '#e3e8ee';
  const totalIntervalos = linea.etiquetas.length;
  const sinRostro = [];
  for (let i = 0; i < totalIntervalos; i++) {
    const hayDatos = emociones.some((e) => linea.series[e.clave][i] !== null);
    sinRostro.push(hayDatos ? null : 100);
  }

  const conjuntos = emociones
    .filter((e) => linea.series[e.clave].some((v) => v))
    .map((e) => ({
      label: nombre(e),
      data: linea.series[e.clave],
      backgroundColor: e.color,
      borderColor: '#ffffff',
      borderWidth: { top: 1 },
      borderSkipped: false,
    }));
  if (sinRostro.some((v) => v !== null)) {
    conjuntos.push({
      label: 'Sin rostro',
      data: sinRostro,
      backgroundColor: COLOR_SIN_ROSTRO,
      borderWidth: 0,
    });
  }

  new Chart(document.getElementById('grafico-tiempo'), {
    type: 'bar',
    data: { labels: linea.etiquetas, datasets: conjuntos },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      datasets: { bar: { barPercentage: 1, categoryPercentage: 0.92 } },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          title: { display: true, text: 'Tiempo desde el inicio (mm:ss)' },
          ticks: { maxRotation: 0, autoSkip: true, autoSkipPadding: 12 },
        },
        y: {
          stacked: true, min: 0, max: 100,
          ticks: { stepSize: 25, callback: (v) => v + '%' },
          title: { display: true, text: '% de muestras' },
        },
      },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12 } },
        tooltip: {
          // Solo se listan las emociones presentes en ese intervalo.
          filter: (item) => item.parsed.y > 0,
          callbacks: {
            title: (items) => 'Segundo ' + items[0].label,
            label: (ctx) => ctx.dataset.label === 'Sin rostro'
              ? ' No se detectó ningún rostro'
              : ' ' + ctx.dataset.label + ': ' + Math.round(ctx.parsed.y) + '%',
          },
        },
      },
    },
  });

  // Dona con el total de muestras por emoción.
  const conDatos = emociones
    .map((e, i) => ({ e: e, total: datos.distribucion[i] }))
    .filter((x) => x.total > 0);
  new Chart(document.getElementById('grafico-distribucion'), {
    type: 'doughnut',
    data: {
      labels: conDatos.map((x) => nombre(x.e)),
      datasets: [{
        data: conDatos.map((x) => x.total),
        backgroundColor: conDatos.map((x) => x.e.color),
        borderColor: '#ffffff',
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              return ' ' + ctx.raw + ' muestras (' + Math.round((100 * ctx.raw) / total) + '%)';
            },
          },
        },
      },
    },
  });
})();
