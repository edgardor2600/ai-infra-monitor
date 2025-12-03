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
  Legend
);

function ProcessMonitor() {
  const { id } = useParams();
  const [processes, setProcesses] = useState([]);
  const [selectedProcess, setSelectedProcess] = useState(null);
  const [processHistory, setProcessHistory] = useState([]);
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
      const data = await getTopProcesses(id, 10, activeTab);
      setProcesses(data);
      setError(null);
      setLoading(false);
    } catch (err) {
      setError('Failed to load processes: ' + err.message);
      setLoading(false);
    }
  };

  const loadProcessHistory = async (processName) => {
    try {
      const data = await getProcessHistory(processName, id, 1);
      setProcessHistory(data);
    } catch (err) {
      console.error('Failed to load process history:', err);
    }
  };

  const handleProcessClick = (process) => {
    setSelectedProcess(process);
  };

  const filteredProcesses = processes.filter(p =>
    p.process_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return <div className="loading">Loading processes...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  // Chart data for selected process
  const chartData = selectedProcess && processHistory.length > 0 ? {
    labels: processHistory.map(h => new Date(h.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'CPU %',
        data: processHistory.map(h => h.cpu_percent),
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        tension: 0.1,
        yAxisID: 'y',
      },
      {
        label: 'Memory (MB)',
        data: processHistory.map(h => h.memory_mb),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
        tension: 0.1,
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
      },
      title: {
        display: true,
        text: selectedProcess ? `${selectedProcess.process_name} - Historical Metrics` : 'Select a process',
      },
    },
    scales: {
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        title: {
          display: true,
          text: 'CPU %',
        },
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        title: {
          display: true,
          text: 'Memory (MB)',
        },
        grid: {
          drawOnChartArea: false,
        },
      },
    },
  };

  return (
    <div className="process-monitor">
      <div className="header">
        <Link to={`/hosts/${id}`} className="back-link">← Back to Host</Link>
        <h1>Process Monitor - Host {id}</h1>
      </div>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'cpu' ? 'active' : ''}`}
          onClick={() => setActiveTab('cpu')}
        >
          Top by CPU
        </button>
        <button
          className={`tab ${activeTab === 'memory' ? 'active' : ''}`}
          onClick={() => setActiveTab('memory')}
        >
          Top by Memory
        </button>
      </div>

      <div className="search-box">
        <input
          type="text"
          placeholder="Search processes..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="content-grid">
        <div className="process-table-container">
          <h2>Processes</h2>
          <table className="process-table">
            <thead>
              <tr>
                <th>Process Name</th>
                <th>PID</th>
                <th>CPU %</th>
                <th>Memory (MB)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredProcesses.map((process) => (
                <tr
                  key={`${process.pid}-${process.process_name}`}
                  className={selectedProcess?.pid === process.pid ? 'selected' : ''}
                  onClick={() => handleProcessClick(process)}
                >
                  <td className="process-name">{process.process_name}</td>
                  <td>{process.pid}</td>
                  <td>
                    <div className="metric-cell">
                      <span>{process.cpu_percent.toFixed(1)}%</span>
                      <div className="progress-bar">
                        <div
                          className="progress-fill cpu"
                          style={{ width: `${Math.min(process.cpu_percent, 100)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="metric-cell">
                      <span>{process.memory_mb.toFixed(0)} MB</span>
                      <div className="progress-bar">
                        <div
                          className="progress-fill memory"
                          style={{ width: `${Math.min((process.memory_mb / 1024) * 10, 100)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`status-badge ${process.status}`}>
                      {process.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredProcesses.length === 0 && (
            <div className="no-data">No processes found</div>
          )}
        </div>

        <div className="chart-container">
          {chartData ? (
            <Line data={chartData} options={chartOptions} />
          ) : (
            <div className="no-selection">
              <p>Click on a process to view its historical metrics</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProcessMonitor;
