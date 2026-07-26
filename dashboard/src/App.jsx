import { BrowserRouter as Router, Routes, Route, Link, useNavigate, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import HostsList from './pages/HostsList';
import HostDetail from './pages/HostDetail';
import AlertsFeed from './pages/AlertsFeed';
import ProcessMonitor from './pages/ProcessMonitor';
import DiskAnalyzer from './pages/DiskAnalyzer';
import Login from './pages/Login';
import './App.css';

const NavigationBar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null; // Hide navigation bar if user is not logged in

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/" className="nav-brand">⚡ AI Infra Monitor</Link>
        <div className="nav-links" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Link to="/dashboard" className="nav-link">📊 Dashboard</Link>
          <Link to="/hosts" className="nav-link">🖥️ Hosts</Link>
          <Link to="/alerts" className="nav-link">🔔 Alertas</Link>
          <Link to="/disk-analyzer" className="nav-link" style={{ background: '#3b82f6', color: 'white', padding: '0.4rem 0.8rem', borderRadius: '6px', fontWeight: '600' }}>
            💾 Disk Analyzer AI
          </Link>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: '#f1f5f9', padding: '0.35rem 0.9rem', borderRadius: '20px', fontSize: '0.85rem' }}>
            <span style={{ fontWeight: '800', color: '#0f172a' }}>
              👤 {user.email} <span style={{ color: '#2563eb', fontWeight: '700' }}>[{user.license_tier}]</span>
            </span>
            {user.organization_name && (
              <span style={{ color: '#64748b', fontSize: '0.8rem' }}>({user.organization_name})</span>
            )}
            <button
              onClick={handleLogout}
              style={{ background: '#ef4444', color: 'white', border: 'none', padding: '0.25rem 0.6rem', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', fontSize: '0.8rem' }}
            >
              🚪 Salir
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

const PublicLoginRoute = () => {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) {
    return <Navigate to="/disk-analyzer" replace />;
  }
  return <Login />;
};

function AppContent() {
  return (
    <div className="app">
      <NavigationBar />
      <main className="main-content">
        <Routes>
          <Route path="/login" element={<PublicLoginRoute />} />
          
          {/* Protected Routes - require active user session */}
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/hosts" element={<ProtectedRoute><HostsList /></ProtectedRoute>} />
          <Route path="/hosts/:id" element={<ProtectedRoute><HostDetail /></ProtectedRoute>} />
          <Route path="/hosts/:id/processes" element={<ProtectedRoute><ProcessMonitor /></ProtectedRoute>} />
          <Route path="/alerts" element={<ProtectedRoute><AlertsFeed /></ProtectedRoute>} />
          <Route path="/disk-analyzer" element={<ProtectedRoute><DiskAnalyzer /></ProtectedRoute>} />

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}

export default App;
