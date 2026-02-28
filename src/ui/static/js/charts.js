// 轻量封装 Chart.js 创建常用图表
// 依赖 CDN: https://cdn.jsdelivr.net/npm/chart.js

function createLineChart(ctx, label, data, color = '#3b82f6') {
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map((_, i) => i + 1),
      datasets: [{
        label,
        data,
        borderColor: color,
        backgroundColor: color + '33',
        tension: 0.3,
        fill: true,
        pointRadius: 0
      }]
    },
    options: {
      animation: false,
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { display: true, grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8', callback: v => v.toFixed ? v.toFixed(2) : v } }
      }
    }
  });
}

function createBarChart(ctx, labels, data, color = '#10b981') {
  return new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ data, backgroundColor: color + 'cc' }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { grid: { color: 'rgba(148,163,184,0.08)' } } } }
  });
}

function updateChart(chart, data) {
  chart.data.datasets[0].data = data;
  chart.data.labels = data.map((_, i) => i + 1);
  chart.update('none');
}

function sparkline(el, data, color = '#3b82f6') {
  return new Chart(el, {
    type: 'line',
    data: { labels: data.map((_, i) => i + 1), datasets: [{ data, borderColor: color, tension: 0.25, pointRadius: 0, borderWidth: 1, fill: false }] },
    options: { animation: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } }
  });
}
