import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardOverview } from '../api';
import './Dashboard.css';

function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadOverview();
    
    // Refresh every 10 seconds
    const interval = setInterval(loadOverview, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadOverview = async () => {
    try {
      const data = await getDashboardOverview();
      setOverview(data);
      setError(null);
      setLoading(false);
    } catch (err) {
      setError('Failed to load dashboard: ' + err.message);
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  const getSeverityClass = (severity) => {
    return `severity-${severity.toLowerCase()}`;
  };

  const getHostStatus = (host) => {
    const lastSeen = new Date(host.last_seen);
    const now = new Date();
    const minutesAgo = (now - lastSeen) / 1000 / 60;
    
    if (minutesAgo > 5) return 'offline';
    if (host.alert_count > 0) return 'warning';
    return 'healthy';
  };

  return (
    <div className="dashboard">
      <h1>Infrastructure Overview</h1>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <div className="card-icon">🖥️</div>
          <div className="card-content">
            <div className="card-value">{overview.total_hosts}</div>
            <div className="card-label">Monitored Hosts</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="card-icon">⚠️</div>
          <div className="card-content">
            <div className="card-value">{overview.total_active_alerts}</div>
            <div className="card-label">Active Alerts</div>
          </div>
        </div>

        <div className="summary-card severity-high">
          <div className="card-icon">🔴</div>
          <div className="card-content">
            <div className="card-value">{overview.alerts_by_severity.HIGH}</div>
            <div className="card-label">High Severity</div>
          </div>
        </div>

        <div className="summary-card severity-medium">
          <div className="card-icon">🟡</div>
          <div className="card-content">
            <div className="card-value">{overview.alerts_by_severity.MEDIUM}</div>
            <div className="card-label">Medium Severity</div>
          </div>
        </div>
      </div>

      {/* Hosts Status Grid */}
      <div className="section">
        <div className="section-header">
          <h2>Hosts Status</h2>
          <Link to="/hosts" className="view-all-link">View All →</Link>
        </div>
        
        <div className="hosts-grid">
          {overview.hosts_status.map((host) => {
            const status = getHostStatus(host);
            return (
              <Link 
                key={host.id} 
                to={`/hosts/${host.id}`} 
                className={`host-status-card ${status}`}
              >
                <div className="host-header">
                  <div className="host-name">{host.hostname}</div>
                  <div className={`status-indicator ${status}`}></div>
                </div>
                
                <div className="host-metrics">
                  <div className="metric">
                    <span className="metric-label">CPU</span>
                    <span className="metric-value">{parseFloat(host.cpu_percent).toFixed(1)}%</span>
                  </div>
                  <div className="metric">
                    <span className="metric-label">Memory</span>
                    <span className="metric-value">{parseFloat(host.mem_percent).toFixed(1)}%</span>
                  </div>
                </div>

                {host.alert_count > 0 && (
                  <div className="host-alerts">
                    {host.alert_count} active alert{host.alert_count !== 1 ? 's' : ''}
                  </div>
                )}

                <div className="host-footer">
                  Last seen: {new Date(host.last_seen).toLocaleTimeString()}
                </div>
              </Link>
            );
          })}
        </div>

        {overview.hosts_status.length === 0 && (
          <div className="no-data">No hosts registered yet</div>
        )}
      </div>

      {/* Recent Alerts */}
      <div className="section">
        <div className="section-header">
          <h2>Recent Alerts</h2>
          <Link to="/alerts" className="view-all-link">View All →</Link>
        </div>

        <div className="recent-alerts">
          {overview.recent_alerts.map((alert) => (
            <div key={alert.id} className="alert-item">
              <span className={`severity-badge ${getSeverityClass(alert.severity)}`}>
                {alert.severity}
              </span>
              <div className="alert-details">
                <div className="alert-host">{alert.hostname}</div>
                <div className="alert-message">{alert.message}</div>
              </div>
              <div className="alert-time">
                {new Date(alert.created_at).toLocaleString()}
              </div>
            </div>
          ))}

          {overview.recent_alerts.length === 0 && (
            <div className="no-data">No active alerts</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
