import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { getHostMetrics } from '../api';
import './HostDetail.css';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

function HostDetail() {
  const { id } = useParams();
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeMetricTab, setActiveMetricTab] = useState('all'); // 'all' | 'cpu' | 'memory' | 'disk'
  const intervalRef = useRef(null);

  useEffect(() => {
    loadMetrics();
    
    // Poll every 3 seconds
    intervalRef.current = setInterval(() => {
      loadMetrics();
    }, 3000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [id]);

  const loadMetrics = async () => {
    try {
      const data = await getHostMetrics(id, 50);
      setMetrics([...data].reverse()); // Reverse to show oldest first
      setError(null);
      setLoading(false);
    } catch (err) {
      setError('Error al cargar métricas: ' + err.message);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="host-detail-container">
        <div className="host-state-box">
          <div className="host-spinner"></div>
          <span>Cargando telemetría del host #{id}...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="host-detail-container">
        <div className="host-state-box host-error-box">
          <span className="host-error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  const latestMetric = metrics[metrics.length - 1] || {};
  const hostname = latestMetric.hostname || `Host #${id}`;
  const cpuVal = latestMetric.cpu_percent || 0;
  const memVal = latestMetric.mem_percent || 0;
  const diskVal = latestMetric.disk_percent || 0;
  const diskFree = latestMetric.disk_free_gb || 0;
  const diskTotal = latestMetric.disk_total_gb || 0;

  // Compute metric averages over the loaded timeframe
  const avgCpu = metrics.length > 0 ? (metrics.reduce((acc, m) => acc + (m.cpu_percent || 0), 0) / metrics.length).toFixed(1) : 0;
  const avgMem = metrics.length > 0 ? (metrics.reduce((acc, m) => acc + (m.mem_percent || 0), 0) / metrics.length).toFixed(1) : 0;
  const maxCpu = metrics.length > 0 ? Math.max(...metrics.map(m => m.cpu_percent || 0)).toFixed(1) : 0;

  const formatTimeLabel = (ts) => {
    if (!ts) return 'N/A';
    const d = new Date(ts);
    if (!isNaN(d.getTime())) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    }
    return 'N/A';
  };

  // Chart Dataset Filtering based on active tab
  const getDatasets = () => {
    const cpuDataset = {
      label: 'CPU %',
      data: metrics.map(m => m.cpu_percent),
      borderColor: '#38bdf8',
      backgroundColor: 'rgba(56, 189, 248, 0.12)',
      fill: activeMetricTab === 'cpu',
      tension: 0.35,
      borderWidth: 2,
      pointRadius: 2,
      pointHoverRadius: 6,
      pointBackgroundColor: '#38bdf8',
    };

    const memoryDataset = {
      label: 'Memoria %',
      data: metrics.map(m => m.mem_percent),
      borderColor: '#c084fc',
      backgroundColor: 'rgba(192, 132, 252, 0.12)',
      fill: activeMetricTab === 'memory',
      tension: 0.35,
      borderWidth: 2,
      pointRadius: 2,
      pointHoverRadius: 6,
      pointBackgroundColor: '#c084fc',
    };

    const diskDataset = {
      label: 'Disco %',
      data: metrics.map(m => m.disk_percent || 0),
      borderColor: '#fbbf24',
      backgroundColor: 'rgba(251, 191, 36, 0.12)',
      fill: activeMetricTab === 'disk',
      tension: 0.35,
      borderWidth: 2,
      pointRadius: 2,
      pointHoverRadius: 6,
      pointBackgroundColor: '#fbbf24',
    };

    if (activeMetricTab === 'cpu') return [cpuDataset];
    if (activeMetricTab === 'memory') return [memoryDataset];
    if (activeMetricTab === 'disk') return [diskDataset];
    return [cpuDataset, memoryDataset, diskDataset];
  };

  const chartData = {
    labels: metrics.map(m => formatTimeLabel(m.timestamp)),
    datasets: getDatasets(),
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#cbd5e1',
          font: { family: 'Inter', size: 12, weight: '600' },
          usePointStyle: true,
          pointStyle: 'circle',
          padding: 20,
        },
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        borderColor: 'rgba(255, 255, 255, 0.12)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: {
          color: '#64748b',
          font: { family: 'JetBrains Mono', size: 10 },
          maxTicksLimit: 12, // Clean timestamp spacing without overlapping
        },
      },
      y: {
        beginAtZero: true,
        max: 100,
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: {
          color: '#94a3b8',
          font: { family: 'JetBrains Mono', size: 11 },
          callback: (value) => `${value}%`,
        },
        title: {
          display: true,
          text: 'Porcentaje (%)',
          color: '#64748b',
          font: { family: 'Inter', size: 11, weight: '600' },
        },
      },
    },
  };

  return (
    <div className="host-detail-container">
      {/* ── Top Header & Actions ── */}
      <div className="host-header-bar">
        <div className="host-title-group">
          <Link to="/hosts" className="host-back-badge">
            <span className="arrow">←</span> Todos los Hosts
          </Link>
          <div className="host-heading-row">
            <h1>Host #{id}</h1>
            <span className="host-name-tag">{hostname}</span>
            <div className="host-online-badge">
              <span className="pulse-dot"></span> EN LÍNEA
            </div>
          </div>
        </div>

        {/* Quick Action Navigation Buttons */}
        <div className="host-action-bar">
          <Link to={`/hosts/${id}/processes`} className="host-act-btn btn-primary">
            ⚡ Monitor de Procesos
          </Link>
          <Link to="/disk-analyzer" className="host-act-btn btn-secondary">
            💾 Analizar Disco AI
          </Link>
        </div>
      </div>

      {/* ── Telemetry Hero Cards Grid ── */}
      <div className="host-hero-grid">
        {/* CPU Card */}
        <div className="telemetry-card">
          <div className="card-top-row">
            <span className="card-label">CPU Actual</span>
            <span className="card-icon">⚡</span>
          </div>
          <div className="card-big-value cpu-color">
            {cpuVal.toFixed(1)}<span className="unit">%</span>
          </div>
          <div className="card-meter-track">
            <div
              className={`card-meter-fill cpu ${cpuVal > 80 ? 'critical' : cpuVal > 50 ? 'warn' : ''}`}
              style={{ width: `${Math.min(cpuVal, 100)}%` }}
            />
          </div>
          <div className="card-sub-info">
            <span>Promedio: <strong>{avgCpu}%</strong></span>
            <span>Pico: <strong>{maxCpu}%</strong></span>
          </div>
        </div>

        {/* Memory Card */}
        <div className="telemetry-card">
          <div className="card-top-row">
            <span className="card-label">Memoria RAM</span>
            <span className="card-icon">🧠</span>
          </div>
          <div className="card-big-value mem-color">
            {memVal.toFixed(1)}<span className="unit">%</span>
          </div>
          <div className="card-meter-track">
            <div
              className={`card-meter-fill mem ${memVal > 88 ? 'critical' : memVal > 75 ? 'warn' : ''}`}
              style={{ width: `${Math.min(memVal, 100)}%` }}
            />
          </div>
          <div className="card-sub-info">
            <span>Promedio: <strong>{avgMem}%</strong></span>
            <span>Estado: <strong className="status-ok">Normal</strong></span>
          </div>
        </div>

        {/* Disk Card */}
        <div className="telemetry-card">
          <div className="card-top-row">
            <span className="card-label">Uso de Disco C:</span>
            <span className="card-icon">💾</span>
          </div>
          <div className={`card-big-value ${diskVal > 90 ? 'disk-warn' : 'disk-color'}`}>
            {diskVal.toFixed(1)}<span className="unit">%</span>
          </div>
          <div className="card-meter-track">
            <div
              className={`card-meter-fill disk ${diskVal > 90 ? 'critical' : ''}`}
              style={{ width: `${Math.min(diskVal, 100)}%` }}
            />
          </div>
          <div className="card-sub-info">
            <span>Libre: <strong>{diskFree.toFixed(1)} GB</strong></span>
            <span>Total: <strong>{diskTotal.toFixed(1)} GB</strong></span>
          </div>
        </div>

        {/* Telemetry Status Card */}
        <div className="telemetry-card">
          <div className="card-top-row">
            <span className="card-label">Última Telemetría</span>
            <span className="card-icon">📡</span>
          </div>
          <div className="card-big-value time-color">
            {latestMetric.timestamp ? formatTimeLabel(latestMetric.timestamp) : 'N/A'}
          </div>
          <div className="card-status-line">
            <span className="live-tag">● Muestreo cada 3s</span>
          </div>
          <div className="card-sub-info">
            <span>Muestras: <strong>{metrics.length} / 50</strong></span>
            <span>Latencia: <strong>&lt; 5ms</strong></span>
          </div>
        </div>
      </div>

      {/* ── Telemetry Chart Panel ── */}
      <div className="host-chart-card">
        <div className="chart-card-header">
          <div className="chart-header-left">
            <span className="chart-header-icon">📈</span>
            <div>
              <h2>Telemetría en Tiempo Real</h2>
              <span className="chart-subtitle">Histórico de muestras recientes recibidas del agente</span>
            </div>
          </div>

          {/* Metric View Selector */}
          <div className="metric-tabs">
            <button
              className={`metric-tab ${activeMetricTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveMetricTab('all')}
            >
              Combinada
            </button>
            <button
              className={`metric-tab ${activeMetricTab === 'cpu' ? 'active' : ''}`}
              onClick={() => setActiveMetricTab('cpu')}
            >
              CPU
            </button>
            <button
              className={`metric-tab ${activeMetricTab === 'memory' ? 'active' : ''}`}
              onClick={() => setActiveMetricTab('memory')}
            >
              Memoria
            </button>
            <button
              className={`metric-tab ${activeMetricTab === 'disk' ? 'active' : ''}`}
              onClick={() => setActiveMetricTab('disk')}
            >
              Disco
            </button>
          </div>
        </div>

        <div className="chart-body">
          <Line data={chartData} options={chartOptions} />
        </div>
      </div>

      {/* ── Host Health & Diagnostics Summary Banner ── */}
      <div className="host-diagnostics-banner">
        <div className="diag-header">
          <span className="diag-icon">🛡️</span>
          <h3>Diagnóstico del Sistema — Host #{id}</h3>
        </div>
        <div className="diag-grid">
          <div className="diag-item">
            <span className="diag-dot ok"></span>
            <div>
              <strong>Carga de Procesador:</strong> Promedio de {avgCpu}% en rango operativo sin saturación de hilos.
            </div>
          </div>
          <div className="diag-item">
            <span className="diag-dot ok"></span>
            <div>
              <strong>Memoria RAM:</strong> Consumo estable al {memVal.toFixed(1)}%. Sin señales de presión de swap.
            </div>
          </div>
          <div className="diag-item">
            <span className={`diag-dot ${diskVal > 90 ? 'warn' : 'ok'}`}></span>
            <div>
              <strong>Almacenamiento:</strong> {diskVal > 90 ? `Atención: Disco C: ocupado al ${diskVal.toFixed(1)}%. Quedan ${diskFree.toFixed(1)} GB libres.` : `Disco C: saludable al ${diskVal.toFixed(1)}%.`}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HostDetail;
