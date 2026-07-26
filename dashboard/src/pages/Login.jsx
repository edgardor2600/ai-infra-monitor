import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Login = () => {
  const navigate = useNavigate();
  const { login, register } = useAuth();

  const [mode, setMode] = useState('login'); // 'login' or 'register'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [organizationName, setOrganizationName] = useState('');
  const [licenseTier, setLicenseTier] = useState('pro_saas');

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      if (mode === 'login') {
        await login(email, password);
        navigate('/disk-analyzer');
      } else {
        const orgName = organizationName.trim() || email.split('@')[0];
        await register(orgName, email, password, licenseTier);
        navigate('/disk-analyzer');
      }
    } catch (err) {
      console.error('Auth error:', err);
      const detail = err.response?.data?.detail || 'Error en la autenticación. Intenta nuevamente.';
      setErrorMsg(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page-container">
      <div className="login-glass-card">
        <div className="login-header">
          <h2>🛡️ AI Infra Monitor B2B</h2>
          <p>{mode === 'login' ? 'Inicia sesión con tu cuenta corporativa' : 'Registra tu empresa y activa tu prueba SaaS'}</p>
        </div>

        <div className="login-tabs">
          <button
            className={`login-tab-btn ${mode === 'login' ? 'active' : ''}`}
            onClick={() => { setMode('login'); setErrorMsg(''); }}
          >
            🔑 Iniciar Sesión
          </button>
          <button
            className={`login-tab-btn ${mode === 'register' ? 'active' : ''}`}
            onClick={() => { setMode('register'); setErrorMsg(''); }}
          >
            🏢 Registrar Empresa
          </button>
        </div>

        {errorMsg && (
          <div className="login-error-alert">
            ⚠️ {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="login-form-group">
            <label>🔑 Correo Electrónico (Identificador Único de Cuenta):</label>
            <input
              type="email"
              className="login-form-input"
              required
              placeholder="tu_correo@dominio.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          {mode === 'register' && (
            <>
              <div className="login-form-group">
                <label>🏢 Nombre de la Organización / Empresa (Opcional):</label>
                <input
                  type="text"
                  className="login-form-input"
                  placeholder="Ej. TechCorp Soluciones B2B"
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)}
                />
              </div>

              <div className="login-form-group">
                <label>💎 Plan Inicial Elegido:</label>
                <select
                  className="login-form-select"
                  value={licenseTier}
                  onChange={(e) => setLicenseTier(e.target.value)}
                >
                  <option value="starter">🥉 Starter / Gratuito ($0)</option>
                  <option value="pro_saas">🥈 Pro SaaS Edition ($29/mes) - Recomendado</option>
                  <option value="enterprise">🥇 Enterprise B2B (Personalizado)</option>
                </select>
              </div>
            </>
          )}

          <div className="login-form-group">
            <label>Contraseña:</label>
            <input
              type="password"
              className="login-form-input"
              required
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn-login-submit"
            disabled={loading}
          >
            {loading
              ? 'Procesando...'
              : mode === 'login'
              ? '🚀 Acceder a la Plataforma'
              : '✨ Crear Cuenta & Organización B2B'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
