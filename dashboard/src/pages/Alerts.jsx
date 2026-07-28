import React, { useState, useEffect, useCallback, useRef } from 'react';
import api, { getNotificationSettings, updateNotificationSettings, testWebhook } from '../api';
import './Alerts.css';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const SEV_CONFIG = {
  CRITICAL: { icon: '🔴', label: 'Crítico',     color: '#ff2d55', glow: 'rgba(255,45,85,0.35)' },
  HIGH:     { icon: '🟠', label: 'Alto',         color: '#ff6b00', glow: 'rgba(255,107,0,0.3)' },
  MEDIUM:   { icon: '🟡', label: 'Medio',        color: '#fbbf24', glow: 'rgba(251,191,36,0.25)' },
  LOW:      { icon: '🔵', label: 'Bajo',          color: '#22d3ee', glow: 'rgba(34,211,238,0.2)' },
  INFO:     { icon: '⚪', label: 'Información',   color: '#6366f1', glow: 'rgba(99,102,241,0.2)' },
};

const RULE_LABELS = {
  cpu_sustained:         '💻 CPU Sostenida',
  cpu_anomaly_spike:     '📈 Pico Anómalo CPU',
  memory_critical:       '🧠 Memoria Crítica',
  memory_high_sustained: '🧠 Memoria Alta',
  disk_critical:         '💾 Disco Crítico',
  disk_trend_runaway:    '💾 Tendencia Disco',
  host_silent:           '📡 Host Silencioso',
  legacy:                '⚙️ Sistema',
};

function timeAgo(iso) {
  if (!iso) return '—';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)   return `hace ${Math.round(diff)}s`;
  if (diff < 3600) return `hace ${Math.round(diff / 60)}m`;
  if (diff < 86400) return `hace ${Math.round(diff / 3600)}h`;
  return `hace ${Math.round(diff / 86400)}d`;
}

function formatDuration(secs) {
  if (!secs) return null;
  if (secs < 60)   return `${secs}s`;
  if (secs < 3600) return `${Math.round(secs / 60)}min`;
  return `${Math.round(secs / 3600)}h ${Math.round((secs % 3600) / 60)}min`;
}

function formatAvgResolution(secs) {
  if (!secs) return null;
  if (secs < 3600) return `${Math.round(secs / 60)} min promedio`;
  return `${(secs / 3600).toFixed(1)} h promedio`;
}

/* ─── HealthRing ──────────────────────────────────────────────────────────── */
function HealthRing({ score }) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? '#10b981' : score >= 50 ? '#fbbf24' : '#ff2d55';

  return (
    <div className="health-score-ring">
      <svg width="80" height="80" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r={radius} stroke="rgba(255,255,255,0.06)" strokeWidth="7" fill="none" />
        <circle
          cx="40" cy="40" r={radius}
          stroke={color} strokeWidth="7" fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div className="health-score-value font-mono">
        <span style={{ color }}>{score}</span>
        <span className="health-score-sub">Salud</span>
      </div>
    </div>
  );
}

/* ─── MetricBar ───────────────────────────────────────────────────────────── */
function MetricBar({ pct, severity }) {
  if (pct === null || pct === undefined) return null;
  const color = SEV_CONFIG[severity]?.color ?? '#6366f1';
  return (
    <div className="metric-bar-row">
      <div className="metric-bar-track">
        <div
          className="metric-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}

/* ─── AlertCard ───────────────────────────────────────────────────────────── */
function AlertCard({ alert, onAcknowledge, onResolve }) {
  const [expanded, setExpanded] = useState(false);
  const [actioning, setActioning] = useState(false);
  const sev = alert.severity?.toUpperCase() || 'INFO';
  const status = alert.status || 'open';
  const config = SEV_CONFIG[sev] || SEV_CONFIG.INFO;
  const ruleLabel = RULE_LABELS[alert.rule_name] || alert.rule_name || '⚙️ Sistema';
  const isActive = status === 'open';

  const handleAck = async (e) => {
    e.stopPropagation();
    setActioning(true);
    await onAcknowledge(alert.id);
    setActioning(false);
  };

  const handleResolve = async (e) => {
    e.stopPropagation();
    setActioning(true);
    await onResolve(alert.id);
    setActioning(false);
  };

  return (
    <div className={`alert-card sev-${sev} status-${status}`}>
      {/* ── Card Header ── */}
      <div className="alert-card-header" onClick={() => setExpanded(p => !p)}>
        {/* Severity badge */}
        <div className={`alert-sev-badge sev-${sev}`}>
          <span>{config.icon}</span>
          <span>{config.label}</span>
        </div>

        {/* Main info */}
        <div className="alert-card-main">
          <div className="alert-card-title-row">
            <span className="alert-hostname">
              {alert.hostname || `Host #${alert.host_id}`}
            </span>
            <span className="alert-rule-tag">{ruleLabel}</span>
            {alert.occurrences_count > 1 && (
              <span className="occ-badge">×{alert.occurrences_count} ocurrencias</span>
            )}
          </div>
          <div className="alert-message">{alert.message}</div>
        </div>

        {/* Dynamic Metric Indicator */}
        <div className="alert-card-right">
          <div className="alert-metric-col font-mono">
            {alert.measured_value !== null && alert.measured_value !== undefined ? (
              <>
                <span className="alert-metric-val">{alert.measured_value}%</span>
                <span className="alert-metric-lbl">Métrica Medida</span>
              </>
            ) : (
              <span className="alert-time-lbl">{timeAgo(alert.last_seen_at || alert.created_at)}</span>
            )}
          </div>
          <button className={`expand-btn ${expanded ? 'open' : ''}`}>▾</button>
        </div>
      </div>

      {/* ── Card Drawer (Expanded) ── */}
      {expanded && (
        <div className="alert-card-drawer">
          <MetricBar pct={alert.measured_value} severity={sev} />

          <div className="drawer-grid font-mono">
            <div className="drawer-item">
              <span className="drawer-lbl">Primer registro:</span>
              <span className="drawer-val">{new Date(alert.created_at).toLocaleString()}</span>
            </div>
            {alert.last_seen_at && (
              <div className="drawer-item">
                <span className="drawer-lbl">Última ocurrencia:</span>
                <span className="drawer-val">{new Date(alert.last_seen_at).toLocaleString()} ({timeAgo(alert.last_seen_at)})</span>
              </div>
            )}
            {alert.host_ip && (
              <div className="drawer-item">
                <span className="drawer-lbl">IP Host:</span>
                <span className="drawer-val">{alert.host_ip}</span>
              </div>
            )}
          </div>

          {/* ── Action Buttons ── */}
          {isActive && (
            <div className="alert-actions">
              <button
                className="btn-ack"
                onClick={handleAck}
                disabled={actioning}
              >
                {actioning ? 'Procesando…' : '✓ Reconocer Alerta'}
              </button>
              <button
                className="btn-resolve"
                onClick={handleResolve}
                disabled={actioning}
              >
                {actioning ? 'Procesando…' : '✅ Marcar como Resuelta'}
              </button>
            </div>
          )}

          {status === 'acknowledged' && (
            <div className="alert-actions">
              <span className="ack-status-tag">✓ Reconocida</span>
              <button
                className="btn-resolve"
                onClick={handleResolve}
                disabled={actioning}
              >
                {actioning ? 'Procesando…' : '✅ Marcar como Resuelta'}
              </button>
            </div>
          )}

          {status === 'resolved' && (
            <div className="alert-actions">
              <div style={{ fontSize: '0.85rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                ✅ Incidente resuelto
                {alert.duration_seconds && <span style={{ color: '#64748b' }}>— Duración total: {formatDuration(alert.duration_seconds)}</span>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Skeleton loaders ────────────────────────────────────────────────────── */
function AlertSkeleton() {
  return (
    <div className="alert-skeleton">
      <div className="skeleton-line w-40" />
      <div className="skeleton-line w-80" />
      <div className="skeleton-line w-60" />
    </div>
  );
}

/* ─── Main Alerts Page ────────────────────────────────────────────────────── */
export default function Alerts() {
  const [alerts, setAlerts]       = useState([]);
  const [summary, setSummary]     = useState(null);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState('open');
  const [sevFilter, setSevFilter] = useState(null);
  const [search, setSearch]       = useState('');
  const [error, setError]         = useState(null);

  // Webhook Notification Settings State
  const [showWebhookModal, setShowWebhookModal] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [notificationEmail, setNotificationEmail] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [webhookMsg, setWebhookMsg] = useState(null);

  const handleOpenWebhookModal = async () => {
    setShowWebhookModal(true);
    setWebhookMsg(null);
    try {
      const data = await getNotificationSettings();
      setWebhookUrl(data.webhook_url || '');
      setNotificationEmail(data.notification_email || '');
    } catch (err) {
      console.error('Error fetching notification settings:', err);
    }
  };

  const handleSaveWebhookSettings = async () => {
    setSavingSettings(true);
    setWebhookMsg(null);
    try {
      await updateNotificationSettings({
        webhook_url: webhookUrl,
        notification_email: notificationEmail
      });
      setWebhookMsg({ type: 'success', text: '¡Configuración guardada correctamente!' });
    } catch (err) {
      setWebhookMsg({ type: 'error', text: 'Error al guardar configuración.' });
    } finally {
      setSavingSettings(false);
    }
  };

  const handleTestWebhook = async () => {
    if (!webhookUrl) {
      alert('Ingresa una URL de Webhook válida.');
      return;
    }
    setTestingWebhook(true);
    setWebhookMsg(null);
    try {
      const res = await testWebhook(webhookUrl);
      setWebhookMsg({ type: 'success', text: res.message || '¡Notificación de prueba enviada!' });
    } catch (err) {
      const detail = err.response?.data?.detail || 'No se pudo enviar la prueba.';
      setWebhookMsg({ type: 'error', text: detail });
    } finally {
      setTestingWebhook(false);
    }
  };

  const pollingRef = useRef(null);

  /* ── Data fetchers ── */
  const fetchSummary = useCallback(async () => {
    try {
      const res = await api.get('/alerts/summary');
      setSummary(res.data);
    } catch { /* non-critical */ }
  }, []);

  const fetchAlerts = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const params = { limit: 100 };
      if (statusFilter && statusFilter !== 'all') params.status = statusFilter;
      if (sevFilter) params.severity = sevFilter;
      const res = await api.get('/alerts', { params });
      setAlerts(res.data.alerts || []);
    } catch (err) {
      setError('Error al cargar las alertas. Verifica la conexión con el backend.');
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, sevFilter]);

  /* ── Initial load + polling every 30s ── */
  useEffect(() => {
    fetchSummary();
    fetchAlerts();

    pollingRef.current = setInterval(() => {
      fetchSummary();
      fetchAlerts(true);
    }, 30000);

    return () => clearInterval(pollingRef.current);
  }, [fetchAlerts, fetchSummary]);

  /* ── Alert actions ── */
  const handleAcknowledge = async (id) => {
    try {
      await api.post(`/alerts/${id}/acknowledge`);
      fetchAlerts(true);
      fetchSummary();
    } catch (e) { console.error(e); }
  };

  const handleResolve = async (id) => {
    try {
      await api.post(`/alerts/${id}/resolve`);
      fetchAlerts(true);
      fetchSummary();
    } catch (e) { console.error(e); }
  };

  /* ── Filtering ── */
  const filteredAlerts = alerts.filter(a => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.message?.toLowerCase().includes(q) ||
      a.hostname?.toLowerCase().includes(q) ||
      a.rule_name?.toLowerCase().includes(q) ||
      a.severity?.toLowerCase().includes(q)
    );
  });

  const healthScore = summary?.health_score ?? 100;

  /* ── Severity stat click handler ── */
  const toggleSevFilter = (sev) => {
    setSevFilter(p => p === sev ? null : sev);
  };

  return (
    <div className="alert-center">
      {/* ── Page Header ── */}
      <div className="alert-center-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>⚡ Centro de Alertas</h1>
          <p className="subtitle">
            Sistema inteligente de monitoreo · Deduplicación · Diagnóstico IA · Auto-resolución
          </p>
        </div>
        <button
          onClick={handleOpenWebhookModal}
          style={{
            padding: '0.75rem 1.25rem',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
            color: 'white',
            border: 'none',
            fontWeight: '700',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)'
          }}
        >
          🔔 Configurar Webhooks (Slack / Teams)
        </button>
      </div>

      {/* ── Health Banner ── */}
      <div className="health-banner">
        <div className="health-left">
          <HealthRing score={healthScore} />
          <div className="health-stats">
            <div className="health-stat">
              <span className={`health-stat-value ${summary?.by_severity?.CRITICAL > 0 ? 'value-critical' : 'value-ok'}`}>
                {summary?.by_severity?.CRITICAL ?? 0}
              </span>
              <span className="health-stat-label">Críticos</span>
            </div>
            <div className="health-stat">
              <span className={`health-stat-value ${summary?.by_severity?.HIGH > 0 ? 'value-high' : 'value-ok'}`}>
                {summary?.by_severity?.HIGH ?? 0}
              </span>
              <span className="health-stat-label">Altos</span>
            </div>
            <div className="health-stat">
              <span className={`health-stat-value ${summary?.by_severity?.MEDIUM > 0 ? 'value-medium' : 'value-ok'}`}>
                {summary?.by_severity?.MEDIUM ?? 0}
              </span>
              <span className="health-stat-label">Medios</span>
            </div>
            <div className="health-stat">
              <span className="health-stat-value value-ok">
                {summary?.resolved_today ?? 0}
              </span>
              <span className="health-stat-label">Resueltos Hoy</span>
            </div>
          </div>
        </div>

        <div className="health-right">
          {summary?.avg_resolution_seconds && (
            <div className="avg-resolution">
              ⏱ Resolución promedio:{' '}
              <strong>{formatAvgResolution(summary.avg_resolution_seconds)}</strong>
            </div>
          )}
          <div style={{ fontSize: '0.8rem', color: '#475569' }}>
            {healthScore >= 80 ? '✅ Sistema Saludable' :
             healthScore >= 50 ? '⚠️ Requiere Atención' : '🚨 Estado Crítico'}
          </div>
        </div>
      </div>

      {/* ── Severity Filter Cards ── */}
      <div className="severity-stats-row">
        {Object.entries(SEV_CONFIG).map(([sev, cfg]) => (
          <div
            key={sev}
            className={`sev-stat-card ${sevFilter === sev ? 'active' : ''}`}
            style={{ '--sev-color': cfg.color, '--sev-glow': cfg.glow }}
            onClick={() => toggleSevFilter(sev)}
          >
            <span className="sev-stat-icon">{cfg.icon}</span>
            <div>
              <div className="sev-stat-count" style={{ color: cfg.color }}>
                {summary?.by_severity?.[sev] ?? 0}
              </div>
              <div className="sev-stat-label">{cfg.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Controls ── */}
      <div className="alert-controls">
        {/* Search */}
        <div className="alert-search-wrap">
          <span className="alert-search-icon">🔍</span>
          <input
            type="text"
            placeholder="Buscar por host, regla, mensaje…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Status filters */}
        {['open','acknowledged','resolved','all'].map(s => (
          <button
            key={s}
            className={`alert-filter-btn ${statusFilter === s ? 'active' : ''}`}
            onClick={() => { setStatusFilter(s); setSevFilter(null); }}
          >
            {s === 'open'         ? '● Activas' :
             s === 'acknowledged' ? '✓ Reconocidas' :
             s === 'resolved'     ? '✅ Resueltas' : '≡ Todas'}
          </button>
        ))}

        {/* Refresh */}
        <button
          className={`refresh-btn ${refreshing ? 'spinning' : ''}`}
          onClick={() => { fetchAlerts(true); fetchSummary(); }}
        >
          <span className="refresh-icon">⟳</span>
          Actualizar
        </button>
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{
          background: 'rgba(255,45,85,0.08)', border: '1px solid rgba(255,45,85,0.25)',
          borderRadius: '10px', padding: '1rem 1.25rem', marginBottom: '1.5rem',
          color: '#ff6b8a', fontSize: '0.9rem'
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── Alert Feed ── */}
      <div className="alert-feed">
        {loading ? (
          [1,2,3].map(i => <AlertSkeleton key={i} />)
        ) : filteredAlerts.length === 0 ? (
          <div className="alert-feed-empty">
            <div className="empty-icon">
              {statusFilter === 'open' ? '✅' : '🔍'}
            </div>
            <h3>
              {statusFilter === 'open'
                ? 'Sin alertas activas'
                : 'No se encontraron alertas'}
            </h3>
            <p>
              {statusFilter === 'open'
                ? 'Tu infraestructura está funcionando correctamente.'
                : 'Prueba ajustando los filtros de búsqueda.'}
            </p>
          </div>
        ) : (
          filteredAlerts.map(alert => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
            />
          ))
        )}
      </div>

      {/* ── Footer count ── */}
      {!loading && filteredAlerts.length > 0 && (
        <div style={{ textAlign: 'center', marginTop: '1.5rem', color: '#475569', fontSize: '0.82rem' }}>
          Mostrando {filteredAlerts.length} alerta{filteredAlerts.length !== 1 ? 's' : ''}
          {sevFilter && <> · Filtradas por: <strong style={{ color: SEV_CONFIG[sevFilter]?.color }}>{SEV_CONFIG[sevFilter]?.label}</strong></>}
        </div>
      )}

      {/* ── Webhook Notification Settings Modal ── */}
      {showWebhookModal && (
        <div className="modal-backdrop">
          <div className="modal-card glass-card" style={{ maxWidth: '520px', padding: '2rem' }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: 0, color: '#f8fafc', fontSize: '1.3rem' }}>🔔 Integración de Webhooks Empresariales</h2>
              <button
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.4rem', cursor: 'pointer' }}
                onClick={() => setShowWebhookModal(false)}
              >
                ✕
              </button>
            </div>

            <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: '1.5', marginTop: 0, marginBottom: '1.5rem' }}>
              Recibe notificaciones instantáneas en tus canales de equipo (Slack, Microsoft Teams, Discord o servidores de Webhook personalizados) cuando se dispare una alerta de severidad <strong>CRÍTICA</strong> o <strong>ALTA</strong>.
            </p>

            {webhookMsg && (
              <div style={{
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                marginBottom: '1.25rem',
                fontSize: '0.86rem',
                fontWeight: '600',
                background: webhookMsg.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                border: webhookMsg.type === 'success' ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(239, 68, 68, 0.4)',
                color: webhookMsg.type === 'success' ? '#34d399' : '#f87171'
              }}>
                {webhookMsg.type === 'success' ? '✅' : '⚠️'} {webhookMsg.text}
              </div>
            )}

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '600', color: '#cbd5e1', marginBottom: '0.4rem' }}>
                URL del Webhook (Slack / Teams / Discord)
              </label>
              <input
                type="text"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="Ej. https://hooks.slack.com/services/T00/B00/XXXX"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  borderRadius: '8px',
                  background: 'rgba(30, 41, 59, 0.9)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#f8fafc',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '600', color: '#cbd5e1', marginBottom: '0.4rem' }}>
                Correo de Alertas Corporativas (Opcional)
              </label>
              <input
                type="email"
                value={notificationEmail}
                onChange={(e) => setNotificationEmail(e.target.value)}
                placeholder="devops@tuempresa.com"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  borderRadius: '8px',
                  background: 'rgba(30, 41, 59, 0.9)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#f8fafc',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                onClick={handleTestWebhook}
                disabled={testingWebhook || !webhookUrl}
                style={{
                  padding: '0.75rem 1.25rem',
                  borderRadius: '8px',
                  background: 'rgba(56, 189, 248, 0.15)',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  color: '#38bdf8',
                  fontWeight: '700',
                  cursor: webhookUrl ? 'pointer' : 'not-allowed',
                  opacity: webhookUrl ? 1 : 0.5
                }}
              >
                {testingWebhook ? 'Probando...' : '🧪 Probar Webhook'}
              </button>
              <button
                onClick={handleSaveWebhookSettings}
                disabled={savingSettings}
                style={{
                  padding: '0.75rem 1.5rem',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
                  border: 'none',
                  color: 'white',
                  fontWeight: '700',
                  cursor: 'pointer'
                }}
              >
                {savingSettings ? 'Guardando...' : 'Guardar Cambios'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
