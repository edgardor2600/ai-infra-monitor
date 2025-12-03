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
  Legend
);

function HostDetail() {
  const { id } = useParams();
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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
      setMetrics(data.reverse()); // Reverse to show oldest first
      setError(null);
      setLoading(false);
    } catch (err) {
      setError('Failed to load metrics: ' + err.message);
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading metrics...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  const chartData = {
    labels: metrics.map(m => new Date(m.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'CPU %',
        data: metrics.map(m => m.cpu_percent),
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        tension: 0.1,
        yAxisID: 'y',
      },
      {
        label: 'Memory %',
        data: metrics.map(m => m.mem_percent),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
        tension: 0.1,
        yAxisID: 'y',
      },
      {
        label: 'Disk %',
        data: metrics.map(m => m.disk_percent || 0),
        borderColor: 'rgb(255, 159, 64)',
        backgroundColor: 'rgba(255, 159, 64, 0.2)',
        tension: 0.1,
        yAxisID: 'y',
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: `Host ${id} - Real-time Metrics`,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        title: {
          display: true,
          text: 'Percentage (%)',
        },
      },
    },
  };

  const latestMetric = metrics[metrics.length - 1];

  return (
    <div className="host-detail">
      <div className="header">
        <Link to="/hosts" className="back-link">← Back to Hosts</Link>
        <h1>Host {id} Details</h1>
        <Link to={`/hosts/${id}/processes`} className="processes-link">
          <button className="processes-button">View Processes</button>
        </Link>
      </div>

      <div className="stats-cards">
        <div className="stat-card">
          <h3>Current CPU</h3>
          <div className="stat-value">{latestMetric?.cpu_percent?.toFixed(1) || 'N/A'}%</div>
        </div>
        <div className="stat-card">
          <h3>Current Memory</h3>
          <div className="stat-value">{latestMetric?.mem_percent?.toFixed(1) || 'N/A'}%</div>
        </div>
        <div className="stat-card">
          <h3>Disk Usage</h3>
          <div className="stat-value">{latestMetric?.disk_percent?.toFixed(1) || 'N/A'}%</div>
          <div className="stat-detail">
            {latestMetric?.disk_free_gb?.toFixed(1) || 'N/A'} GB free of {latestMetric?.disk_total_gb?.toFixed(1) || 'N/A'} GB
          </div>
        </div>
        <div className="stat-card">
          <h3>Last Update</h3>
          <div className="stat-value">
            {latestMetric ? new Date(latestMetric.timestamp).toLocaleTimeString() : 'N/A'}
          </div>
        </div>
      </div>

      <div className="chart-container">
        <Line data={chartData} options={chartOptions} />
      </div>
    </div>
  );
}

export default HostDetail;
