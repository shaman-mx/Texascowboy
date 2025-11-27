// static/js/aa_chart.js
// Requires Chart.js loaded before this script.

(function () {
  const CANVAS_ID = 'aaChart';
  const API_URL_BASE = '/api/aa_minutes';

  function minutesToLabel(min) {
    const m = min % (24 * 60);
    const h = Math.floor(m / 60);
    const mm = m % 60;
    return `${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
  }

  function downsample(labels, counts, maxPoints = 1440) {
    const n = counts.length;
    if (n <= maxPoints) return { labels, counts };
    const factor = Math.ceil(n / maxPoints);
    const outLabels = [];
    const outCounts = [];
    for (let i = 0; i < n; i += factor) {
      const slice = counts.slice(i, i + factor);
      const sum = slice.reduce((a, b) => a + b, 0);
      outCounts.push(sum);
      const lastIdx = Math.min(i + factor - 1, n - 1);
      outLabels.push(labels[lastIdx] !== undefined ? labels[lastIdx] : minutesToLabel(lastIdx));
    }
    return { labels: outLabels, counts: outCounts };
  }

  function createLineChart(ctx, labels, counts) {
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Tổng số lần nổ AA',
          data: counts,
          borderColor: 'rgba(26,115,232,0.95)',
          backgroundColor: 'rgba(26,115,232,0.12)',
          pointRadius: 0,
          borderWidth: 1.5,
          fill: true,
          tension: 0.15
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        layout: { padding: { right: 24, bottom: 48 } },
        scales: {
          x: {
            display: true,
            offset: true,
            title: { display: true, text: 'Thời gian' },
            ticks: {
              autoSkip: true,
              maxRotation: 45,
              minRotation: 45,
              align: 'end'
            }
          },
          y: {
            beginAtZero: true,
            title: { display: true, text: 'Tổng số lần' },
            ticks: { precision: 0, stepSize: 1 }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: { mode: 'index', intersect: false }
        }
      }
    });
  }

  async function fetchData(agg = 1) {
    const url = API_URL_BASE + (agg && agg > 1 ? `?agg=${agg}` : '');
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error('Fetch error ' + res.status);
    return res.json();
  }

  async function initChart(opts = {}) {
    const agg = opts.agg || 1;
    const maxPoints = typeof opts.maxPoints === 'number' ? opts.maxPoints : 1440;
    const canvas = document.getElementById(CANVAS_ID);
    if (!canvas) return;

    try {
      const data = await fetchData(agg);
      let labels = Array.isArray(data.labels) ? data.labels.slice() : [];
      let counts = Array.isArray(data.counts) ? data.counts.slice() : [];

      if (labels.length && typeof labels[0] === 'number') {
        labels = labels.map(v => {
          const h = Math.floor(v / 60);
          const m = v % 60;
          return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
        });
      }

      if (counts.length !== labels.length) {
        const n = Math.max(counts.length, labels.length);
        const newLabels = [];
        const newCounts = [];
        for (let i = 0; i < n; i++) {
          newLabels.push(labels[i] !== undefined ? labels[i] : minutesToLabel(i));
          newCounts.push(counts[i] !== undefined ? counts[i] : 0);
        }
        labels = newLabels;
        counts = newCounts;
      }

      const ds = downsample(labels, counts, maxPoints);

      canvas.style.display = 'block';
      canvas.style.width = canvas.style.width || '100%';
      canvas.style.height = canvas.style.height || '320px';
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.floor(canvas.clientWidth * ratio);
      canvas.height = Math.floor(canvas.clientHeight * ratio);

      const ctx = canvas.getContext('2d');
      if (canvas._chartInstance) canvas._chartInstance.destroy();
      canvas._chartInstance = createLineChart(ctx, ds.labels, ds.counts);

      setTimeout(() => {
        try {
          const chart = canvas._chartInstance;
          if (!chart) return;
          const meta = chart.getDatasetMeta(0);
          const lastIndex = chart.data.labels.length - 1;
          if (meta && meta.data && lastIndex >= 0) {
            const lastPoint = meta.data[lastIndex];
            const overflow = lastPoint && chart.chartArea ? Math.round(lastPoint.x - chart.chartArea.right) : 0;
            if (overflow >= 0) {
              const extra = overflow > 0 ? overflow + 8 : 8;
              chart.options.layout = chart.options.layout || {};
              chart.options.layout.padding = chart.options.layout.padding || {};
              chart.options.layout.padding.right = (chart.options.layout.padding.right || 0) + extra;
              chart.update();
            }
          }
        } catch (e) {
          console.warn('Chart post-adjust error', e);
        }
      }, 50);

    } catch (err) {
      console.error('Lỗi khi tải dữ liệu biểu đồ:', err);
      const container = document.getElementById(CANVAS_ID)?.parentElement;
      if (container) {
        let msg = container.querySelector('.chart-error');
        if (!msg) {
          msg = document.createElement('div');
          msg.className = 'chart-error';
          msg.style.color = '#666';
          msg.style.fontSize = '13px';
          msg.style.padding = '8px 0';
          container.appendChild(msg);
        }
        msg.textContent = 'Không có dữ liệu biểu đồ hoặc lỗi tải dữ liệu.';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initChart({ agg: 1, maxPoints: 1440 });
  });

  window.refreshAaChart = function (agg = 1) {
    return initChart({ agg: agg, maxPoints: 1440 });
  };
})();