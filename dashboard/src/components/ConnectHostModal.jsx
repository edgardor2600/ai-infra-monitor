import React, { useState } from 'react';
import './ConnectHostModal.css';

const ConnectHostModal = ({ isOpen, onClose }) => {
  const [copiedOS, setCopiedOS] = useState(null);
  const backendUrl = "https://ai-infra-monitor-api.onrender.com";

  if (!isOpen) return null;

  const winCommand = `git clone https://github.com/edgardor2600/ai-infra-monitor.git && cd ai-infra-monitor && pip install psutil requests httpx && python -m agent run --backend-url ${backendUrl}`;
  const linuxCommand = `git clone https://github.com/edgardor2600/ai-infra-monitor.git && cd ai-infra-monitor && pip install psutil requests httpx && python -m agent run --backend-url ${backendUrl}`;

  const copyToClipboard = (text, osType) => {
    navigator.clipboard.writeText(text);
    setCopiedOS(osType);
    setTimeout(() => setCopiedOS(null), 3000);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content connect-host-modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose}>&times;</button>
        
        <div className="modal-header">
          <div className="modal-header-icon">🚀</div>
          <h2>Conectar Nuevo Servidor o Computadora</h2>
          <p className="modal-subtitle">
            Sigue estos 3 sencillos pasos para empezar a monitorear CPU, RAM, Procesos y Discos en tiempo real.
          </p>
        </div>

        <div className="steps-container">
          {/* STEP 1 */}
          <div className="step-card">
            <div className="step-number">1</div>
            <div className="step-content">
              <h3>Abre la Terminal en la máquina a monitorear</h3>
              <p>Abre PowerShell (Windows) o la Terminal (Linux / Mac / VPS) en el equipo que deseas conectar.</p>
            </div>
          </div>

          {/* STEP 2 */}
          <div className="step-card">
            <div className="step-number">2</div>
            <div className="step-content">
              <h3>Copia y ejecuta el comando de 1 línea</h3>
              
              {/* Windows Tab */}
              <div className="command-box-group">
                <div className="os-badge">🪟 Windows (PowerShell)</div>
                <div className="command-snippet">
                  <code>{winCommand}</code>
                  <button 
                    className={`btn-copy ${copiedOS === 'win' ? 'copied' : ''}`}
                    onClick={() => copyToClipboard(winCommand, 'win')}
                  >
                    {copiedOS === 'win' ? '✓ ¡Copiado!' : '📋 Copiar'}
                  </button>
                </div>
              </div>

              {/* Linux / Mac Tab */}
              <div className="command-box-group">
                <div className="os-badge">🐧 Linux / macOS</div>
                <div className="command-snippet">
                  <code>{linuxCommand}</code>
                  <button 
                    className={`btn-copy ${copiedOS === 'linux' ? 'copied' : ''}`}
                    onClick={() => copyToClipboard(linuxCommand, 'linux')}
                  >
                    {copiedOS === 'linux' ? '✓ ¡Copiado!' : '📋 Copiar'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* STEP 3 */}
          <div className="step-card">
            <div className="step-number">3</div>
            <div className="step-content">
              <h3>¡Conexión Automática!</h3>
              <p>Una vez ejecutado, el agente enviará telemetría y tu servidor aparecerá automáticamente en tu panel web en menos de 5 segundos.</p>
              
              <div className="connection-status-pill">
                <span className="pulse-dot"></span>
                <span>Esperando datos del agente en vivo...</span>
              </div>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-done" onClick={onClose}>
            Entendido, ¡Iré a conectar mi equipo!
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConnectHostModal;
