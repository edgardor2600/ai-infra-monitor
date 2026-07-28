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
import { getTopProcesses, getProcessHistory } from '../api';
import './ProcessMonitor.css';

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

function ProcessMonitor() {
  const { id } = useParams();
  const [processes, setProcesses] = useState([]);
  const [selectedProcess, setSelectedProcess] = useState(null);
  const [processHistory, setProcessHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('cpu');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const intervalRef = useRef(null);

  useEffect(() => {
    loadProcesses();
    
    // Auto-refresh every 5 seconds
    intervalRef.current = setInterval(() => {
      loadProcesses();
    }, 5000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [id, activeTab]);

  useEffect(() => {
    if (selectedProcess) {
      loadProcessHistory(selectedProcess.process_name);
    }
  }, [selectedProcess]);

  const loadProcesses = async () => {
    try {
      const data = await getTopProcesses(id, 15, activeTab);
      setProcesses(data);
      setError(null);
      setLoading(false);
    } catch (err) {
      setError('Error al cargar procesos: ' + err.message);
      setLoading(false);
    }
  };

  const loadProcessHistory = async (processName) => {
    setHistoryLoading(true);
    try {
      const data = await getProcessHistory(processName, id, 1);
      if (data && data.length > 0) {
        setProcessHistory(data);
      } else if (selectedProcess) {
        // Initial live sample fallback if no DB history exists yet
        setProcessHistory([{
          timestamp: new Date().toISOString(),
          process_name: selectedProcess.process_name,
          pid: selectedProcess.pid,
          cpu_percent: selectedProcess.cpu_percent || 0,
          memory_mb: selectedProcess.memory_mb || 0,
          status: selectedProcess.status || 'running'
        }]);
      } else {
        setProcessHistory([]);
      }
    } catch (err) {
      console.error('Failed to load process history:', err);
      if (selectedProcess) {
        setProcessHistory([{
          timestamp: new Date().toISOString(),
          process_name: selectedProcess.process_name,
          pid: selectedProcess.pid,
          cpu_percent: selectedProcess.cpu_percent || 0,
          memory_mb: selectedProcess.memory_mb || 0,
          status: selectedProcess.status || 'running'
        }]);
      } else {
        setProcessHistory([]);
      }
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleProcessClick = (process) => {
    setSelectedProcess(process);
  };

  const filteredProcesses = processes.filter(p =>
    p.process_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Chart data configuration for dark telemetry theme
  const chartData = selectedProcess && processHistory.length > 0 ? {
    labels: processHistory.map(h => h.timestamp ? new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Live'),
    datasets: [
      {
        label: 'CPU %',
        data: processHistory.map(h => h.cpu_percent),
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.12)',
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: '#38bdf8',
        yAxisID: 'y',
      },
      {
        label: 'Memoria (MB)',
        data: processHistory.map(h => h.memory_mb),
        borderColor: '#c084fc',
        backgroundColor: 'rgba(192, 132, 252, 0.12)',
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: '#c084fc',
        yAxisID: 'y1',
      },
    ],
  } : null;

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
          padding: 15
        }
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        borderColor: 'rgba(255, 255, 255, 0.12)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
        displayColors: true,
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
      },
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        title: {
          display: true,
          text: 'CPU %',
          color: '#38bdf8',
          font: { family: 'Inter', size: 11, weight: '600' }
        },
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 11 } }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        title: {
          display: true,
          text: 'Memoria (MB)',
          color: '#c084fc',
          font: { family: 'Inter', size: 11, weight: '600' }
        },
        grid: { drawOnChartArea: false },
        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 11 } }
      },
    },
  };

  if (loading) {
    return (
      <div className="proc-mon-container">
        <div className="proc-state-box">
          <div className="proc-spinner"></div>
          <span>Cargando telemetría de procesos...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="proc-mon-container">
        <div className="proc-state-box proc-error-box">
          <span className="proc-error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="proc-mon-container">
      {/* ── Header Bar ── */}
      <div className="proc-mon-header">
        <div className="proc-mon-title-group">
          <Link to={`/hosts/${id}`} className="proc-back-badge">
            <span className="arrow">←</span> Regresar a Host
          </Link>
          <div className="proc-title-row">
            <h1>Monitor de Procesos</h1>
            <div className="proc-host-badge">
              <span className="proc-live-dot"></span> Host #{id}
            </div>
          </div>
        </div>

        {/* Toolbar: Segmented Controls + Search */}
        <div className="proc-toolbar">
          <div className="proc-segmented-control">
            <button
              className={`segment-btn ${activeTab === 'cpu' ? 'active' : ''}`}
              onClick={() => setActiveTab('cpu')}
            >
              <span className="icon">⚡</span> Mayor CPU
            </button>
            <button
              className={`segment-btn ${activeTab === 'memory' ? 'active' : ''}`}
              onClick={() => setActiveTab('memory')}
            >
              <span className="icon">🧠</span> Mayor Memoria
            </button>
          </div>

          <div className="proc-search-field">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Filtrar por nombre..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            {searchTerm && (
              <button className="clear-search" onClick={() => setSearchTerm('')}>×</button>
            )}
          </div>
        </div>
      </div>

      {/* ── Main Split View ── */}
      <div className="proc-split-grid">
        {/* Left Column: Process Table */}
        <div className="proc-card proc-table-card">
          <div className="proc-card-header">
            <div className="proc-card-title">
              <span className="proc-card-icon">📊</span>
              <h2>Procesos Activos</h2>
              <span className="proc-count-tag">{filteredProcesses.length}</span>
            </div>
            <div className="proc-refresh-indicator">
              <span className="proc-pulse-dot"></span> Actualizando cada 5s
            </div>
          </div>

          <div className="proc-table-wrapper">
            <table className="proc-table">
              <thead>
                <tr>
                  <th>Proceso</th>
                  <th className="num-col">PID</th>
                  <th>CPU %</th>
                  <th>Memoria (MB)</th>
                  <th className="status-col">Estado</th>
                </tr>
              </thead>
              <tbody>
                {filteredProcesses.map((proc) => {
                  const isSelected = selectedProcess?.pid === proc.pid && selectedProcess?.process_name === proc.process_name;
                  const cpuVal = proc.cpu_percent || 0;
                  const memVal = proc.memory_mb || 0;

                  return (
                    <tr
                      key={`${proc.pid}-${proc.process_name}`}
                      className={`proc-row ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleProcessClick(proc)}
                    >
                      <td className="proc-name-cell">
                        <div className="proc-name-wrap">
                          <span className="proc-app-icon">⚙️</span>
                          <span className="proc-name-text" title={proc.process_name}>{proc.process_name}</span>
                        </div>
                      </td>
                      <td className="num-col pid-text">{proc.pid}</td>
                      <td>
                        <div className="proc-metric-meter">
                          <div className="proc-metric-header">
                            <span className={`proc-metric-val ${cpuVal > 20 ? 'high-cpu' : ''}`}>
                              {cpuVal.toFixed(1)}%
                            </span>
                          </div>
                          <div className="proc-bar-track">
                            <div
                              className={`proc-bar-fill cpu ${cpuVal > 50 ? 'critical' : cpuVal > 20 ? 'warn' : ''}`}
                              style={{ width: `${Math.min(cpuVal, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="proc-metric-meter">
                          <div className="proc-metric-header">
                            <span className={`proc-metric-val ${memVal > 1024 ? 'high-mem' : ''}`}>
                              {memVal.toFixed(0)} <span className="unit">MB</span>
                            </span>
                          </div>
                          <div className="proc-bar-track">
                            <div
                              className={`proc-bar-fill memory ${memVal > 2048 ? 'critical' : memVal > 1024 ? 'warn' : ''}`}
                              style={{ width: `${Math.min((memVal / 2048) * 100, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="status-col">
                        <span className={`proc-status-pill ${proc.status.toLowerCase()}`}>
                          <span className="dot"></span>
                          {proc.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredProcesses.length === 0 && (
              <div className="proc-empty-state">
                <span>🔍 No se encontraron procesos coincidentes</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Process Inspector & Historical Telemetry Chart */}
        <div className="proc-card proc-chart-card">
          <div className="proc-card-header">
            <div className="proc-card-title">
              <span className="proc-card-icon">🔬</span>
              <h2>Inspección de Proceso</h2>
            </div>
            {selectedProcess && (
              <div className="proc-selected-badge">
                <span>{selectedProcess.process_name}</span>
                <span className="pid-sub">PID: {selectedProcess.pid}</span>
              </div>
            )}
          </div>

          <div className="proc-chart-wrapper">
            {selectedProcess ? (
              <div className="proc-inspector-content">
                {/* Process Live Info Cards */}
                <div className="proc-info-cards">
                  <div className="proc-stat-box">
                    <span className="stat-label">CPU Actual</span>
                    <span className="stat-val cpu-color">
                      {(selectedProcess.cpu_percent || 0).toFixed(1)}%
                    </span>
                  </div>

                  <div className="proc-stat-box">
                    <span className="stat-label">Memoria Usada</span>
                    <span className="stat-val mem-color">
                      {(selectedProcess.memory_mb || 0).toFixed(0)} <span className="stat-unit">MB</span>
                    </span>
                  </div>

                  <div className="proc-stat-box">
                    <span className="stat-label">Estado</span>
                    <span className="stat-val status-color">
                      {selectedProcess.status || 'running'}
                    </span>
                  </div>

                  <div className="proc-stat-box">
                    <span className="stat-label">Muestras Capturadas</span>
                    <span className="stat-val samples-color">
                      {processHistory.length}
                    </span>
                  </div>
                </div>

                {/* Historical Chart */}
                <div className="chart-inner-wrap">
                  {historyLoading ? (
                    <div className="proc-chart-loading">
                      <div className="proc-spinner"></div>
                      <span>Cargando gráfico de telemetría...</span>
                    </div>
                  ) : chartData ? (
                    <Line data={chartData} options={chartOptions} />
                  ) : (
                    <div className="proc-no-chart-data">
                      <span>📉 Recopilando historial de telemetría para {selectedProcess.process_name}...</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="proc-no-selection-state">
                <div className="proc-inspect-icon">🎯</div>
                <h3>Inspeccionar Proceso</h3>
                <p>Haz clic en cualquier proceso de la lista izquierda para ver sus detalles en tiempo real y gráfica histórica de consumo.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProcessMonitor;
