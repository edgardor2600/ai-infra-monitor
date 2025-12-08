import { useState, useEffect, useRef } from 'react';
import { getAlerts, analyzeAlert, getAlertAnalysis, updateAlertStatus } from '../api';
import './AlertsFeed.css';

function AlertsFeed() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analyzingAlerts, setAnalyzingAlerts] = useState(new Set());
  const [analyses, setAnalyses] = useState({});
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'open', 'acknowledged', 'resolved'
  const intervalRef = useRef(null);
  const analyzingAlertsRef = useRef(new Set());

  // Keep ref in sync with state
  useEffect(() => {
    analyzingAlertsRef.current = analyzingAlerts;
  }, [analyzingAlerts]);

  useEffect(() => {
    loadAlerts();
    
    // Poll for new alerts and analyses every 5 seconds
    intervalRef.current = setInterval(() => {
      loadAlerts();
      checkPendingAnalyses();
    }, 5000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [statusFilter]); // Reload when filter changes

  const loadAlerts = async () => {
    try {
      // If filter is 'all', we need to fetch all statuses
      if (statusFilter === 'all') {
        // Fetch alerts with all statuses
        const [openData, ackData, resolvedData] = await Promise.all([
          getAlerts('open'),
          getAlerts('acknowledged'),
          getAlerts('resolved')
        ]);
        setAlerts([...openData, ...ackData, ...resolvedData]);
      } else {
        const data = await getAlerts(statusFilter);
        setAlerts(data);
      }
      setError(null);
      setLoading(false);
    } catch (err) {
      setError('Failed to load alerts: ' + err.message);
      setLoading(false);
    }
  };

  const handleAnalyze = async (alertId) => {
    try {
      setAnalyzingAlerts(prev => new Set(prev).add(alertId));
      await analyzeAlert(alertId);
      // Start polling for this alert's analysis
      setTimeout(() => checkAnalysis(alertId), 2000);
    } catch (err) {
      alert('Failed to start analysis: ' + err.message);
      setAnalyzingAlerts(prev => {
        const newSet = new Set(prev);
        newSet.delete(alertId);
        return newSet;
      });
    }
  };

  const checkAnalysis = async (alertId) => {
    try {
      const analysis = await getAlertAnalysis(alertId);
      if (analysis) {
        setAnalyses(prev => ({ ...prev, [alertId]: analysis }));
        setAnalyzingAlerts(prev => {
          const newSet = new Set(prev);
          newSet.delete(alertId);
          return newSet;
        });
      }
    } catch (err) {
      console.error('Error checking analysis:', err);
    }
  };

  const checkPendingAnalyses = () => {
    // Use ref to get current value
    analyzingAlertsRef.current.forEach(alertId => {
      checkAnalysis(alertId);
    });
  };

  const getSeverityClass = (severity) => {
    return `severity-${severity.toLowerCase()}`;
  };

  const handleStatusUpdate = async (alertId, newStatus) => {
    try {
      await updateAlertStatus(alertId, newStatus);
      // Reload alerts to reflect the change
      await loadAlerts();
    } catch (err) {
      alert('Failed to update alert status: ' + err.message);
    }
  };

  if (loading) {
    return <div className="loading">Loading alerts...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="alerts-feed">
      <div className="alerts-feed-header">
        <h1>Alerts Feed</h1>
        
        {/* Status Filter Tabs */}
        <div className="filter-tabs">
          <button
            className={`filter-tab ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            All
          </button>
          <button
            className={`filter-tab ${statusFilter === 'open' ? 'active' : ''}`}
            onClick={() => setStatusFilter('open')}
          >
            Open
          </button>
          <button
            className={`filter-tab ${statusFilter === 'acknowledged' ? 'active' : ''}`}
            onClick={() => setStatusFilter('acknowledged')}
          >
            Acknowledged
          </button>
          <button
            className={`filter-tab ${statusFilter === 'resolved' ? 'active' : ''}`}
            onClick={() => setStatusFilter('resolved')}
          >
            Resolved
          </button>
        </div>
      </div>
      
      <div className="alerts-list">
        {alerts.map((alert) => {
          const isAnalyzing = analyzingAlerts.has(alert.id);
          const analysis = analyses[alert.id];
          
          return (
            <div key={alert.id} className="alert-card">
              <div className="alert-header">
                <div className="alert-info">
                  <span className={`severity-badge ${getSeverityClass(alert.severity)}`}>
                    {alert.severity}
                  </span>
                  <span className={`status-badge status-${alert.status}`}>
                    {alert.status}
                  </span>
                  <span className="metric-name">{alert.metric_name}</span>
                  <span className="timestamp">
                    {new Date(alert.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="alert-actions">
                  {!analysis && (
                    <button
                      onClick={() => handleAnalyze(alert.id)}
                      disabled={isAnalyzing}
                      className="btn-analyze"
                    >
                      {isAnalyzing ? 'Analyzing...' : 'Analyze'}
                    </button>
                  )}
                  {alert.status === 'open' && (
                    <button
                      onClick={() => handleStatusUpdate(alert.id, 'acknowledged')}
                      className="btn-acknowledge"
                    >
                      Acknowledge
                    </button>
                  )}
                  {(alert.status === 'open' || alert.status === 'acknowledged') && (
                    <button
                      onClick={() => handleStatusUpdate(alert.id, 'resolved')}
                      className="btn-resolve"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
              
              <div className="alert-message">{alert.message}</div>
              
              {isAnalyzing && (
                <div className="analysis-pending">
                  <div className="spinner"></div>
                  <span>AI is analyzing this alert...</span>
                </div>
              )}
              
              {analysis && (
                <div className="analysis-result">
                  <h3>AI Analysis</h3>
                  <div className="analysis-section">
                    <strong>Summary:</strong>
                    <p>{analysis.result.summary}</p>
                  </div>
                  <div className="analysis-section">
                    <strong>Possible Causes:</strong>
                    <ul>
                      {analysis.result.causes.map((cause, idx) => (
                        <li key={idx}>{cause}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="analysis-section">
                    <strong>Recommendations:</strong>
                    <ul>
                      {analysis.result.recommendations.map((rec, idx) => (
                        <li key={idx}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="confidence">
                    Confidence: {(analysis.result.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          );
        })}
        
        {alerts.length === 0 && (
          <div className="no-data">No open alerts</div>
        )}
      </div>
    </div>
  );
}

export default AlertsFeed;
