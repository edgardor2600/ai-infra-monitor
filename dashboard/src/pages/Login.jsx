import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  IconZap,
  IconServer,
  IconShield,
  IconCpu,
  IconHardDrive,
  IconActivity,
  IconLock,
  IconMail,
  IconBuilding,
  IconBot,
  IconClock,
  IconCheckCircle,
  IconArrowRight,
  IconLayers
} from '../components/Icons';
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
        const u = await login(email, password);
        if (u?.role === 'superadmin') {
          navigate('/admin');
        } else {
          navigate('/disk-analyzer');
        }
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

  const scrollToSection = (sectionId) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const scrollToLogin = () => {
    scrollToSection('login-form-section');
  };

  return (
    <div className="landing-page-root">
      {/* Top Brand Navigation Bar */}
      <header className="landing-navbar">
        <div className="landing-nav-container">
          <div className="landing-brand">
            <IconZap size={24} color="#38bdf8" className="brand-logo-icon" />
            <span className="brand-name">
              AI Infra Monitor <span className="brand-badge font-mono">ENTERPRISE</span>
            </span>
          </div>

          <nav className="landing-nav-links">
            <button className="nav-link-btn" onClick={() => scrollToSection('features')}>Características</button>
            <button className="nav-link-btn" onClick={() => scrollToSection('security-section')}>Seguridad</button>
            <button className="nav-link-btn" onClick={() => scrollToSection('pricing')}>Planes SaaS</button>
          </nav>

          <div className="landing-nav-actions">
            <button className="nav-btn-outline" onClick={() => { setMode('login'); scrollToLogin(); }}>
              Iniciar Sesión
            </button>
            <button className="nav-btn-primary" onClick={() => { setMode('register'); scrollToLogin(); }}>
              Probar Gratis
            </button>
          </div>
        </div>
      </header>

      {/* Hero & Login Section */}
      <section className="landing-hero-section">
        <div className="hero-container">
          {/* Left Column: Value Proposition */}
          <div className="hero-content">
            <div className="hero-badge">
              <IconShield size={15} color="#38bdf8" />
              <span>Plataforma Inteligente de Infraestructura B2B</span>
            </div>
            
            <h1 className="hero-title">
              Monitoreo de Infraestructura, <span className="text-gradient">Alertas Autónomas</span> y Limpieza con IA
            </h1>
            
            <p className="hero-description">
              Solución enterprise para supervisión en tiempo real de servidores, diagnósticos automáticos impulsados por IA y mantenimiento preventivo de espacio en disco.
            </p>

            <div className="hero-kpi-highlights">
              <div className="kpi-box">
                <span className="kpi-num">99.9%</span>
                <span className="kpi-text">Disponibilidad SLA</span>
              </div>
              <div className="kpi-box">
                <span className="kpi-num">&lt; 3s</span>
                <span className="kpi-text">Telemetría en Vivo</span>
              </div>
              <div className="kpi-box">
                <span className="kpi-num">1-Clic</span>
                <span className="kpi-text">Rollback Seguro</span>
              </div>
            </div>

            <div className="hero-cta-group">
              <button className="btn-hero-primary" onClick={() => { setMode('register'); scrollToLogin(); }}>
                Registrar Empresa <IconArrowRight size={18} />
              </button>
              <button className="btn-hero-secondary" onClick={() => { setMode('login'); scrollToLogin(); }}>
                Acceso Corporativo
              </button>
            </div>
          </div>

          {/* Right Column: Sleek Login Card */}
          <div className="hero-login-wrapper" id="login-form-section">
            <div className="login-glass-card">
              <div className="login-header">
                <h2>Portal de Acceso SaaS</h2>
                <p>
                  {mode === 'login'
                    ? 'Ingresa tus credenciales para acceder a la consola'
                    : 'Crea tu cuenta de empresa y activa tu prueba gratuita'}
                </p>
              </div>

              <div className="login-tabs">
                <button
                  className={`login-tab-btn ${mode === 'login' ? 'active' : ''}`}
                  onClick={() => { setMode('login'); setErrorMsg(''); }}
                >
                  Iniciar Sesión
                </button>
                <button
                  className={`login-tab-btn ${mode === 'register' ? 'active' : ''}`}
                  onClick={() => { setMode('register'); setErrorMsg(''); }}
                >
                  Registrar Empresa
                </button>
              </div>

              {errorMsg && (
                <div className="login-error-alert">
                  {errorMsg}
                </div>
              )}

              <form onSubmit={handleSubmit}>
                <div className="login-form-group">
                  <label>Correo Electrónico Corporativo</label>
                  <div className="input-with-icon">
                    <IconMail size={18} className="input-icon" />
                    <input
                      type="email"
                      className="login-form-input"
                      required
                      placeholder="usuario@empresa.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                </div>

                {mode === 'register' && (
                  <>
                    <div className="login-form-group">
                      <label>Nombre de la Organización</label>
                      <div className="input-with-icon">
                        <IconBuilding size={18} className="input-icon" />
                        <input
                          type="text"
                          className="login-form-input"
                          placeholder="Ej. TechCorp Soluciones"
                          value={organizationName}
                          onChange={(e) => setOrganizationName(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="login-form-group">
                      <label>Plan Inicial Elegido</label>
                      <div className="input-with-icon">
                        <IconLayers size={18} className="input-icon" />
                        <select
                          className="login-form-select"
                          value={licenseTier}
                          onChange={(e) => setLicenseTier(e.target.value)}
                        >
                          <option value="starter">Starter / Gratuito ($0)</option>
                          <option value="pro_saas">Pro SaaS Edition ($29/mes) - Recomendado</option>
                          <option value="enterprise">Enterprise B2B (Personalizado)</option>
                        </select>
                      </div>
                    </div>
                  </>
                )}

                <div className="login-form-group">
                  <label>Contraseña</label>
                  <div className="input-with-icon">
                    <IconLock size={18} className="input-icon" />
                    <input
                      type="password"
                      className="login-form-input"
                      required
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn-login-submit"
                  disabled={loading}
                >
                  {loading
                    ? 'Procesando...'
                    : mode === 'login'
                    ? 'Acceder a la Consola'
                    : 'Crear Cuenta & Empezar'}
                </button>
              </form>

              <div className="login-footer-note">
                <IconLock size={13} color="#64748b" /> Conexión segura de grado bancario con JWT Signed Tokens.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Showcase Grid Section */}
      <section className="landing-features-section" id="features">
        <div className="section-container">
          <div className="section-header">
            <span className="section-tag">TECNOLOGÍA DE VANGUARDIA</span>
            <h2 className="section-title">Todo lo que tu infraestructura necesita en un solo lugar</h2>
            <p className="section-subtitle">
              Diseñado para desarrolladores, DevOps y administradores de sistemas que exigen alta precisión y control total.
            </p>
          </div>

          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon-wrapper cyan">
                <IconActivity size={26} color="#38bdf8" />
              </div>
              <h3>Métricas en Tiempo Real</h3>
              <p>Visualiza el uso de CPU, memoria RAM, estado del disco e IOPS de tus servidores con telemetría interactiva de alta fidelidad.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon-wrapper purple">
                <IconBot size={26} color="#c084fc" />
              </div>
              <h3>Diagnóstico Autónomo con IA</h3>
              <p>Integración con Google Gemini AI y MiniMax para analizar alertas complejas, diagnosticar cuellos de botella y sugerir remediación.</p>
            </div>

            <div className="feature-card" id="analyzer">
              <div className="feature-icon-wrapper amber">
                <IconHardDrive size={26} color="#f59e0b" />
              </div>
              <h3>Disk Analyzer AI Pro</h3>
              <p>Detector de archivos duplicados por SHA-256, depurador de cachés de desarrollo (pip, npm) y visualización Treemap interactiva.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon-wrapper green">
                <IconShield size={26} color="#10b981" />
              </div>
              <h3>Respaldos & Rollback Seguro</h3>
              <p>Cada operación de limpieza genera un respaldo estructurado con manifiesto JSON, permitiendo restaurar archivos en 1-clic.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon-wrapper rose">
                <IconClock size={26} color="#f43f5e" />
              </div>
              <h3>Mantenimiento Programado</h3>
              <p>Configura tareas periódicas de limpieza automática para categorías de cero riesgo (temporales, cachés web, papelera) evitando discos llenos.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon-wrapper blue">
                <IconBuilding size={26} color="#60a5fa" />
              </div>
              <h3>Arquitectura Multi-Tenant B2B</h3>
              <p>Aislamiento estricto de datos por empresa, asignación granular de roles y auditoría inmutable de operaciones.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Security & Compliance B2B Dedicated Section */}
      <section className="landing-security-section" id="security-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-tag">SEGURIDAD B2B & CUMPLIMIENTO</span>
            <h2 className="section-title">Protección de datos de grado bancario y privacidad total</h2>
            <p className="section-subtitle">
              Diseñado bajo estrictos estándares de aislamiento multi-tenant, autenticación con tokens firmados JWT y auditoría de operaciones.
            </p>
          </div>

          <div className="security-grid">
            <div className="security-card">
              <div className="security-icon-wrapper green">
                <IconShield size={28} color="#10b981" />
              </div>
              <h3>Aislamiento Multi-Tenant Estricto</h3>
              <p>Cada organización cuenta con su propio esquema lógico aislado en PostgreSQL, evitando cualquier fuga o cruce involuntario de datos entre empresas.</p>
            </div>

            <div className="security-card">
              <div className="security-icon-wrapper blue">
                <IconLock size={28} color="#3b82f6" />
              </div>
              <h3>Tokens Firmados JWT & Cifrado HMAC</h3>
              <p>Sesiones autenticadas mediante tokens HS256 con expiración previa, firmas HMAC y contraseñas encriptadas con algoritmos PBKDF2 de alta seguridad.</p>
            </div>

            <div className="security-card">
              <div className="security-icon-wrapper purple">
                <IconBuilding size={28} color="#c084fc" />
              </div>
              <h3>Modo 100% Offline (Sin Nube)</h3>
              <p>Opción de despliegue local con proveedores de IA privados sin enviar código fuente ni documentos fuera de tu red corporativa.</p>
            </div>
          </div>
        </div>
      </section>

      {/* SaaS Pricing Plans Section */}
      <section className="landing-pricing-section" id="pricing">
        <div className="section-container">
          <div className="section-header">
            <span className="section-tag">PLANES & SUSCRIPCIONES</span>
            <h2 className="section-title">Elige el plan ideal para escalar tu infraestructura</h2>
            <p className="section-subtitle">
              Sin contratos forzosos. Cambia o ajusta tu nivel de licencia en cualquier momento desde tu consola.
            </p>
          </div>

          <div className="pricing-grid">
            {/* Starter Plan */}
            <div className="pricing-card">
              <div className="pricing-badge">STARTER</div>
              <h3>Starter Edition</h3>
              <div className="price-tag">$0 <span className="period">/ mes</span></div>
              <p className="plan-desc">Para entornos personales y servidores pequeños.</p>
              <ul className="plan-features">
                <li><IconCheckCircle size={16} color="#10b981" /> Monitoreo básico de hasta 10 hosts</li>
                <li><IconCheckCircle size={16} color="#10b981" /> Escaneo inteligente de espacio en disco</li>
                <li><IconCheckCircle size={16} color="#10b981" /> Limpieza manual de cachés</li>
                <li><IconCheckCircle size={16} color="#10b981" /> Registro de alertas básicas</li>
              </ul>
              <button className="btn-plan" onClick={() => { setMode('register'); setLicenseTier('starter'); scrollToLogin(); }}>
                Comenzar Gratis
              </button>
            </div>

            {/* Pro SaaS Plan */}
            <div className="pricing-card popular">
              <div className="popular-ribbon">RECOMENDADO</div>
              <div className="pricing-badge pro">PRO SAAS</div>
              <h3>Pro SaaS Edition</h3>
              <div className="price-tag">$29 <span className="period">/ mes</span></div>
              <p className="plan-desc">La solución profesional completa para empresas.</p>
              <ul className="plan-features">
                <li><IconCheckCircle size={16} color="#38bdf8" /> Todo lo del plan Starter</li>
                <li><IconCheckCircle size={16} color="#38bdf8" /> <strong>Diagnóstico de Alertas con IA (Gemini)</strong></li>
                <li><IconCheckCircle size={16} color="#38bdf8" /> <strong>Buscador de duplicados por SHA-256</strong></li>
                <li><IconCheckCircle size={16} color="#38bdf8" /> <strong>Visualizador Treemap de almacenamiento</strong></li>
                <li><IconCheckCircle size={16} color="#38bdf8" /> <strong>Mantenimiento programado (Cron jobs)</strong></li>
              </ul>
              <button className="btn-plan primary" onClick={() => { setMode('register'); setLicenseTier('pro_saas'); scrollToLogin(); }}>
                Activar Pro SaaS
              </button>
            </div>

            {/* Enterprise Plan */}
            <div className="pricing-card enterprise">
              <div className="pricing-badge enterprise">ENTERPRISE</div>
              <h3>Enterprise B2B</h3>
              <div className="price-tag">Personalizado</div>
              <p className="plan-desc">Para grandes organizaciones e infraestructura crítica.</p>
              <ul className="plan-features">
                <li><IconCheckCircle size={16} color="#c084fc" /> Todo lo del plan Pro SaaS</li>
                <li><IconCheckCircle size={16} color="#c084fc" /> Hosts monitoreados ilimitados</li>
                <li><IconCheckCircle size={16} color="#c084fc" /> Auditoría inmutable de limpiezas</li>
                <li><IconCheckCircle size={16} color="#c084fc" /> Integración de IA Privada (Air-Gapped)</li>
                <li><IconCheckCircle size={16} color="#c084fc" /> Soporte técnico prioritario 24/7</li>
              </ul>
              <button className="btn-plan" onClick={() => { setMode('register'); setLicenseTier('enterprise'); scrollToLogin(); }}>
                Contactar Ventas
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-container">
          <div className="footer-brand">
            <IconZap size={20} color="#38bdf8" /> AI Infra Monitor Enterprise B2B
          </div>
          <p>© 2026 AI Infrastructure Monitor. Plataforma de monitoreo y optimización de infraestructura B2B.</p>
        </div>
      </footer>
    </div>
  );
};

export default Login;
