import { BrowserRouter as Router, Routes, Route, NavLink, Link, useNavigate, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import HostsList from './pages/HostsList';
import HostDetail from './pages/HostDetail';
import Alerts from './pages/Alerts';
import ProcessMonitor from './pages/ProcessMonitor';
import DiskAnalyzer from './pages/DiskAnalyzer';
import Login from './pages/Login';
import SuperAdmin from './pages/SuperAdmin';
import './App.css';

import { useState } from 'react';
import ConnectHostModal from './components/ConnectHostModal';

const NavigationBar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isConnectOpen, setIsConnectOpen] = useState(false);

  if (!user) return null; // Hide navigation bar if user is not logged in

  const isSuperAdmin = user.role === 'superadmin' || user.email === 'admin@admin.com' || user.email === 'erq2600@gmail.com';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <>
      <nav className="navbar">
        <div className="nav-container">
          <Link to="/" className="nav-brand">
            <span className="nav-brand-icon">⚡</span> AI Infra Monitor
          </Link>
          
          <div className="nav-links">
            <NavLink
              to="/dashboard"
              className={({ isActive }) => `nav-link ${isActive || location.pathname === '/' ? 'active' : ''}`}
            >
              📊 Dashboard
            </NavLink>
            
            <NavLink
              to="/hosts"
              className={({ isActive }) => `nav-link ${isActive || location.pathname.startsWith('/hosts') ? 'active' : ''}`}
            >
              🖥️ Hosts
            </NavLink>

            <NavLink
              to="/alerts"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              🔔 Alertas
            </NavLink>

            <NavLink
              to="/disk-analyzer"
              className={({ isActive }) => `nav-link nav-link-disk-analyzer ${isActive ? 'active' : ''}`}
            >
              💾 Disk Analyzer AI
            </NavLink>

            <button 
              onClick={() => setIsConnectOpen(true)} 
              className="nav-link nav-btn-connect-host"
              style={{
                background: 'linear-gradient(135deg, #10b981, #059669)',
                color: '#ffffff',
                border: 'none',
                padding: '6px 14px',
                borderRadius: '8px',
                fontWeight: '600',
                cursor: 'pointer',
                boxShadow: '0 2px 10px rgba(16, 185, 129, 0.3)',
                marginRight: '8px'
              }}
            >
              ➕ Conectar Servidor
            </button>

            {isSuperAdmin && (
              <NavLink
                to="/admin"
                className={({ isActive }) => `nav-link nav-link-superadmin ${isActive ? 'active' : ''}`}
              >
                👑 SuperAdmin
              </NavLink>
            )}
            
            <div className="nav-user-pill">
              <span className="user-email-text">👤 {user.email}</span>
              <span className="user-tier-badge">[{user.license_tier || 'STARTER'}]</span>
              {user.organization_name && (
                <span className="user-org-name">({user.organization_name})</span>
              )}
              <button onClick={handleLogout} className="nav-logout-btn">
                🚪 Salir
              </button>
            </div>
          </div>
        </div>
      </nav>

      <ConnectHostModal 
        isOpen={isConnectOpen} 
        onClose={() => setIsConnectOpen(false)} 
      />
    </>
  );
};

const PublicLoginRoute = () => {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) {
    if (user.role === 'superadmin' || user.email === 'admin@admin.com' || user.email === 'erq2600@gmail.com') {
      return <Navigate to="/admin" replace />;
    }
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
          <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
          <Route path="/disk-analyzer" element={<ProtectedRoute><DiskAnalyzer /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><SuperAdmin /></ProtectedRoute>} />

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
