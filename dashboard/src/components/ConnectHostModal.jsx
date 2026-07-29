import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './ConnectHostModal.css';

const ConnectHostModal = ({ isOpen, onClose }) => {
  const [copiedOS, setCopiedOS] = useState(null);
  const { user } = useAuth();
  const orgId = user?.org_id || 1;
  const backendUrl = "https://ai-infra-monitor-api.onrender.com";

  if (!isOpen) return null;

  const winCmdCommand = `pip install psutil && python -c "import os, urllib.request; os.environ['AGENT_ORG_ID']='${orgId}'; exec(urllib.request.urlopen('https://raw.githubusercontent.com/edgardor2600/ai-infra-monitor/main/agent/standalone_agent.py').read())"`;
  const winPsCommand = `$env:AGENT_ORG_ID="${orgId}"; pip install psutil; python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/edgardor2600/ai-infra-monitor/main/agent/standalone_agent.py').read())"`;
  const linuxCommand = `export AGENT_ORG_ID="${orgId}" && pip install psutil && python3 -c "import os, urllib.request; os.environ['AGENT_ORG_ID']='${orgId}'; exec(urllib.request.urlopen('https://raw.githubusercontent.com/edgardor2600/ai-infra-monitor/main/agent/standalone_agent.py').read())"`;

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
              <p>Abre <strong>CMD</strong> o <strong>PowerShell</strong> (Windows), o la <strong>Terminal</strong> (Linux / macOS / VPS) en el equipo que deseas conectar.</p>
            </div>
          </div>

          {/* STEP 2 */}
          <div className="step-card">
            <div className="step-number">2</div>
            <div className="step-content">
              <h3>Copia y ejecuta el comando de 1 línea según tu terminal</h3>
              
              {/* Windows CMD Tab */}
              <div className="command-box-group">
                <div className="os-badge">🪟 Windows (CMD - Símbolo del Sistema)</div>
                <div className="command-snippet">
                  <code>{winCmdCommand}</code>
                  <button 
                    className={`btn-copy ${copiedOS === 'wincmd' ? 'copied' : ''}`}
                    onClick={() => copyToClipboard(winCmdCommand, 'wincmd')}
                  >
                    {copiedOS === 'wincmd' ? '✓ ¡Copiado!' : '📋 Copiar'}
                  </button>
                </div>
              </div>

              {/* Windows PowerShell Tab */}
              <div className="command-box-group">
                <div className="os-badge">⚡ Windows (PowerShell)</div>
                <div className="command-snippet">
                  <code>{winPsCommand}</code>
                  <button 
                    className={`btn-copy ${copiedOS === 'winps' ? 'copied' : ''}`}
                    onClick={() => copyToClipboard(winPsCommand, 'winps')}
                  >
                    {copiedOS === 'winps' ? '✓ ¡Copiado!' : '📋 Copiar'}
                  </button>
                </div>
              </div>

              {/* Linux / Mac Tab */}
              <div className="command-box-group">
                <div className="os-badge">🐧 Linux / macOS / VPS</div>
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
