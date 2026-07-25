import React, { useState, useEffect } from 'react';
import api, { inspectBackup } from '../api';
import './DiskAnalyzer.css';

const DiskAnalyzer = () => {
  const [drives, setDrives] = useState([]);
  const [selectedDrive, setSelectedDrive] = useState('C:');
  const [scans, setScans] = useState([]);
  const [currentScan, setCurrentScan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [cleanupInProgress, setCleanupInProgress] = useState(false);
  const [cleanupHistory, setCleanupHistory] = useState([]);
  const [showCleanupHistory, setShowCleanupHistory] = useState(false);
  
  // AI Analysis state
  const [aiReport, setAiReport] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [openPreviews, setOpenPreviews] = useState({});

  // Purge Backup Modal state
  const [purgeModal, setPurgeModal] = useState({
    isOpen: false,
    item: null,
    loading: false,
    aiAnalysis: null,
    backupInfo: null
  });

  const togglePreview = (categoryName) => {
    setOpenPreviews(prev => ({ ...prev, [categoryName]: !prev[categoryName] }));
  };

  useEffect(() => {
    fetchDrives();
    fetchScans();
    fetchCleanupHistory();
  }, []);

  useEffect(() => {
    if (scanning && currentScan) {
      const interval = setInterval(() => {
        fetchScanDetails(currentScan.scan_id);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [scanning, currentScan]);

  const fetchDrives = async () => {
    try {
      const response = await api.get('/disk-analyzer/drives');
      const availableDrives = response.data.drives || [];
      setDrives(availableDrives);
      if (availableDrives.length > 0 && !selectedDrive) {
        setSelectedDrive(availableDrives[0].device || 'C:');
      }
    } catch (error) {
      console.error('Error fetching drives:', error);
    }
  };

  const fetchScans = async () => {
    try {
      const response = await api.get('/disk-analyzer/scans?limit=10');
      setScans(response.data.scans || []);
    } catch (error) {
      console.error('Error fetching scans:', error);
    }
  };

  const fetchScanDetails = async (scanId) => {
    try {
      const response = await api.get(`/disk-analyzer/scan/${scanId}`);
      setCurrentScan(response.data);
      if (response.data.status === 'completed' || response.data.status === 'failed') {
        setScanning(false);
      }
    } catch (error) {
      console.error('Error fetching scan details:', error);
      setScanning(false);
    }
  };

  const startScan = async () => {
    setLoading(true);
    setScanning(true);
    setAiReport(null);
    
    try {
      const hostsResponse = await api.get('/hosts');
      const hosts = hostsResponse.data.hosts || [];
      
      if (hosts.length === 0) {
        alert('No se encontraron hosts. Asegúrate de que el agente esté en ejecución.');
        setLoading(false);
        setScanning(false);
        return;
      }

      const hostId = hosts[0].id;
      const response = await api.post('/disk-analyzer/scan', {
        host_id: hostId,
        drive: selectedDrive
      });

      if (response.data.ok) {
        const scanId = response.data.scan_id;
        await fetchScanDetails(scanId);
        await fetchScans();
      }
    } catch (error) {
      console.error('Error starting scan:', error);
      alert('Error al iniciar el escaneo.');
      setScanning(false);
    } finally {
      setLoading(false);
    }
  };

  const requestAIAnalysis = async () => {
    if (!currentScan) return;
    setAiLoading(true);
    try {
      const response = await api.post('/disk-analyzer/analyze-ai', {
        scan_id: currentScan.scan_id
      });
      if (response.data.ok) {
        setAiReport(response.data.ai_report);
      }
    } catch (error) {
      console.error('Error in AI analysis:', error);
      alert('No se pudo generar el análisis MiniMax AI. Verifica la configuración de tu API Key.');
    } finally {
      setAiLoading(false);
    }
  };

  const fetchCleanupHistory = async () => {
    try {
      const response = await api.get('/disk-analyzer/cleanups?limit=20');
      setCleanupHistory(response.data.operations || []);
    } catch (error) {
      console.error('Error fetching cleanup history:', error);
    }
  };

  const handleOpenPurgeModal = async (cleanupItem) => {
    setPurgeModal({
      isOpen: true,
      item: cleanupItem,
      loading: true,
      aiAnalysis: null,
      backupInfo: null
    });

    try {
      const response = await inspectBackup(cleanupItem.backup_path);
      if (response.ok) {
        setPurgeModal(prev => ({
          ...prev,
          loading: false,
          aiAnalysis: response.ai_analysis,
          backupInfo: response.backup_info
        }));
      }
    } catch (err) {
      console.error('Error inspecting backup with AI:', err);
      setPurgeModal(prev => ({ ...prev, loading: false }));
    }
  };

  const handleConfirmPurge = async () => {
    if (!purgeModal.item) return;
    try {
      const response = await api.post('/disk-analyzer/purge-backup', {
        backup_path: purgeModal.item.backup_path
      });
      if (response.data.success) {
        setPurgeModal({ isOpen: false, item: null, loading: false, aiAnalysis: null, backupInfo: null });
        await fetchCleanupHistory();
      }
    } catch (error) {
      console.error('Error purging backup:', error);
      alert('No se pudo eliminar la carpeta de respaldo.');
    }
  };

  const performRollback = async (operationId, backupPath) => {
    const confirmRollback = window.confirm(
      `¿Deseas restaurar los archivos eliminados desde la copia de respaldo?\n\nUbicación: ${backupPath}`
    );

    if (!confirmRollback) return;

    try {
      const response = await api.post('/disk-analyzer/rollback', {
        operation_id: operationId
      });

      if (response.data.ok) {
        alert(`Restauración completada con éxito. Archivos restaurados: ${response.data.files_restored}`);
        await fetchCleanupHistory();
      }
    } catch (error) {
      console.error('Error performing rollback:', error);
      alert('Fallo al realizar la restauración.');
    }
  };

  const toggleCategory = (categoryName) => {
    setSelectedCategories(prev => {
      if (prev.includes(categoryName)) {
        return prev.filter(c => c !== categoryName);
      } else {
        return [...prev, categoryName];
      }
    });
  };

  const performCleanup = async () => {
    if (selectedCategories.length === 0) {
      alert('Selecciona al menos una categoría para limpiar');
      return;
    }

    const confirmCleanup = window.confirm(
      `¿Estás seguro de que deseas limpiar ${selectedCategories.length} categorías seleccionadas?\n\nCategorías:\n${selectedCategories.join(', ')}\n\nSe aplicarán las reglas de seguridad automáticas.`
    );

    if (!confirmCleanup) return;

    setCleanupInProgress(true);

    try {
      const response = await api.post('/disk-analyzer/cleanup', {
        scan_id: currentScan.scan_id,
        categories: selectedCategories,
        create_backup: true
      });

      if (response.data.ok) {
        alert(
          `Limpieza completada con éxito!\n\n` +
          `Archivos borrados: ${response.data.files_deleted}\n` +
          `Espacio liberado: ${formatBytes(response.data.size_freed)}\n` +
          `Copia de seguridad guardada en: ${response.data.backup_path}`
        );

        await fetchScanDetails(currentScan.scan_id);
        await fetchScans();
        await fetchCleanupHistory();
        setSelectedCategories([]);
      }
    } catch (error) {
      console.error('Error performing cleanup:', error);
      alert('Error al realizar la limpieza.');
    } finally {
      setCleanupInProgress(false);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const getRiskLevelClass = (riskLevel) => {
    switch (riskLevel) {
      case 'low':
        return 'risk-low';
      case 'medium':
        return 'risk-medium';
      case 'high':
        return 'risk-high';
      default:
        return 'risk-low';
    }
  };

  return (
    <div className="disk-analyzer">
      <div className="disk-analyzer-header">
        <h1>Análisis y Limpieza Inteligente de Disco (MiniMax AI)</h1>
        <p className="subtitle">Escaneo profundo, 100% seguro y optimización de almacenamiento</p>
      </div>

      <div className="controls-card">
        <div className="drive-selector-container">
          <label htmlFor="drive-select">Unidad de Disco:</label>
          <select
            id="drive-select"
            value={selectedDrive}
            onChange={(e) => setSelectedDrive(e.target.value)}
            disabled={scanning || loading}
          >
            {drives.length > 0 ? (
              drives.map((d) => (
                <option key={d.device} value={d.device}>
                  {d.device} ({d.used_percent}% usado - {formatBytes(d.free)} libres)
                </option>
              ))
            ) : (
              <option value="C:">Disco C: (Principal)</option>
            )}
          </select>
        </div>

        <button
          className="btn-primary"
          onClick={startScan}
          disabled={loading || scanning}
        >
          {scanning ? 'Escaneando Disco...' : 'Iniciar Escaneo Completo'}
        </button>
      </div>

      {currentScan && (
        <div className="scan-results">
          <div className="scan-header">
            <h2>Resultados del Escaneo ({currentScan.categories?.drive || selectedDrive})</h2>
            <div className="scan-status">
              <span className={`status-badge status-${currentScan.status}`}>
                {currentScan.status}
              </span>
              {currentScan.total_size && (
                <span className="total-size">
                  Espacio total recuperable: {formatBytes(currentScan.total_size)}
                </span>
              )}
            </div>
          </div>

          {currentScan.disk_info && (
            <div className="disk-space-widget">
              <h3>💾 Estado del Disco ({currentScan.disk_info.drive || selectedDrive})</h3>
              <div className="disk-stats">
                <div className="disk-stat">
                  <span className="disk-label">Total</span>
                  <span className="disk-value">{formatBytes(currentScan.disk_info.total)}</span>
                </div>
                <div className="disk-stat">
                  <span className="disk-label">Usado</span>
                  <span className="disk-value">{formatBytes(currentScan.disk_info.used)}</span>
                </div>
                <div className="disk-stat">
                  <span className="disk-label">Libre</span>
                  <span className="disk-value free">{formatBytes(currentScan.disk_info.free)}</span>
                </div>
              </div>
              <div className="disk-progress-bar">
                <div 
                  className="disk-progress-fill"
                  style={{ width: `${currentScan.disk_info.used_percent}%` }}
                >
                  <span className="disk-progress-text">{currentScan.disk_info.used_percent}% Usado</span>
                </div>
              </div>
            </div>
          )}

          {currentScan.status === 'completed' && (
            <div className="ai-section">
              <button 
                className="btn-ai-analyze" 
                onClick={requestAIAnalysis}
                disabled={aiLoading}
              >
                {aiLoading ? 'Generando Informe MiniMax AI...' : '🤖 Analizar con MiniMax AI'}
              </button>

              {aiReport && (
                <div className="ai-report-card">
                  <div className="ai-report-header">
                    <h3>🤖 {aiReport.title || 'Diagnóstico MiniMax AI'}</h3>
                    <span className="ai-status-tag">{aiReport.overall_status}</span>
                  </div>
                  <p className="ai-explanation">{aiReport.explanation_es}</p>
                  <div className="ai-safety-alert">
                    🛡️ <strong>Garantía de Seguridad:</strong> {aiReport.safety_guarantee}
                  </div>

                  {aiReport.top_recommendations && (
                    <div className="ai-recommendations">
                      <h4>Recomendaciones Principales:</h4>
                      <ul>
                        {aiReport.top_recommendations.map((rec, i) => (
                          <li key={i}>{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {currentScan.status === 'completed' && currentScan.categories && (
            <div key={`scan-container-${currentScan.scan_id}`}>
              {(() => {
                const categoriesWithFiles = Object.entries(currentScan.categories)
                  .filter(([categoryName, categoryData]) => 
                    categoryName !== 'disk_info' && 
                    categoryName !== 'drive' && 
                    categoryData.file_count > 0
                  );
                
                return categoriesWithFiles.length > 0 ? (
                  <div key="active-categories-block">
                    <div className="categories-grid">
                      {categoriesWithFiles.map(([categoryName, categoryData]) => (
                        <div
                          key={categoryName}
                          className={`category-card ${selectedCategories.includes(categoryName) ? 'selected' : ''}`}
                          onClick={() => toggleCategory(categoryName)}
                        >
                          <div className="category-header">
                            <input
                              type="checkbox"
                              checked={selectedCategories.includes(categoryName)}
                              onChange={() => toggleCategory(categoryName)}
                              onClick={(e) => e.stopPropagation()}
                            />
                            <h3>{categoryData.display_name}</h3>
                            <span className={`risk-badge ${getRiskLevelClass(categoryData.risk_level)}`}>
                              {categoryData.risk_level}
                            </span>
                          </div>

                          <p className="category-description">{categoryData.description}</p>

                          <div className="category-stats">
                            <div className="stat">
                              <span className="stat-label">Archivos:</span>
                              <span className="stat-value">{categoryData.file_count}</span>
                            </div>
                            <div className="stat">
                              <span className="stat-label">Tamaño:</span>
                              <span className="stat-value">{formatBytes(categoryData.total_size)}</span>
                            </div>
                          </div>

                          {categoryData.is_safe_auto && (
                            <div className="safe-badge">
                              ✓ Seguro para limpieza automática
                            </div>
                          )}

                          {/* MiniMax AI Category Insight */}
                          {aiReport?.categories_advice?.[categoryName] && (
                            <div className="ai-category-insight">
                              <div className="ai-insight-header">🤖 Análisis MiniMax AI:</div>
                              {typeof aiReport.categories_advice[categoryName] === 'object' ? (
                                <>
                                  <p className="ai-insight-text"><strong>Contenido:</strong> {aiReport.categories_advice[categoryName].what_it_contains}</p>
                                  <p className="ai-insight-text"><strong>¿Qué se pierde?:</strong> {aiReport.categories_advice[categoryName].what_will_be_lost}</p>
                                </>
                              ) : (
                                <p className="ai-insight-text">{aiReport.categories_advice[categoryName]}</p>
                              )}
                            </div>
                          )}

                          {categoryData.files && categoryData.files.length > 0 && (
                            <div className="file-preview-controlled" onClick={(e) => e.stopPropagation()}>
                              <button
                                type="button"
                                className="btn-preview-toggle"
                                onClick={() => togglePreview(categoryName)}
                              >
                                {openPreviews[categoryName] ? '▼ Ocultar lista' : '▶ Ver lista de archivos'} ({categoryData.files.length} elementos)
                              </button>
                              {openPreviews[categoryName] && (
                                <div className="file-list">
                                  {categoryData.files.slice(0, 10).map((file, idx) => (
                                    <div key={file.path || idx} className="file-item">
                                      <div className="file-path" title={file.path}>
                                        {file.path}
                                      </div>
                                      <div className="file-size">{formatBytes(file.size)}</div>
                                    </div>
                                  ))}
                                  {categoryData.files.length > 10 && (
                                    <div className="file-item more-files">
                                      ... y {categoryData.files.length - 10} archivos más
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    <div className="cleanup-actions">
                      <div className="selected-info">
                        {selectedCategories.length > 0 ? (
                          <p>
                            <strong>{selectedCategories.length}</strong> categorías seleccionadas para limpiar
                          </p>
                        ) : (
                          <p>Selecciona las categorías que deseas limpiar</p>
                        )}
                      </div>
                      <button
                        className="btn-cleanup"
                        onClick={performCleanup}
                        disabled={selectedCategories.length === 0 || cleanupInProgress}
                      >
                        {cleanupInProgress ? 'Limpiando...' : 'Limpiar Seleccionados (Con Backup)'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="all-clean-message" key="all-clean-block">
                    <div className="success-icon">✨</div>
                    <h3>¡Todo Limpio!</h3>
                    <p>No se encontraron elementos de desecho en esta unidad. ¡Tu disco está optimizado!</p>
                  </div>
                );
              })()}
            </div>
          )}

          {currentScan.status === 'running' && (
            <div className="scanning-indicator">
              <div className="spinner"></div>
              <p>Escaneando disco profundamente... Por favor espera.</p>
            </div>
          )}

          {currentScan.status === 'failed' && (
            <div className="error-message">
              <p>Escaneo fallido: {currentScan.error_message}</p>
            </div>
          )}
        </div>
      )}

      {cleanupHistory.length > 0 && (
        <div className="cleanup-history">
          <div className="history-header">
            <h2>Historial de Limpiezas y Respaldos</h2>
            <button 
              className="btn-toggle-history"
              onClick={() => setShowCleanupHistory(!showCleanupHistory)}
            >
              {showCleanupHistory ? 'Ocultar' : 'Mostrar'} Historial
            </button>
          </div>
          
          {showCleanupHistory && (
            <div className="cleanup-list">
              {cleanupHistory.map((cleanup) => (
                <div key={cleanup.operation_id} className="cleanup-item">
                  <div className="cleanup-item-header">
                    <span className="cleanup-id">Limpieza #{cleanup.operation_id}</span>
                    <span className={`status-badge status-${cleanup.status}`}>
                      {cleanup.status}
                    </span>
                  </div>
                  
                  <div className="cleanup-item-details">
                    <div className="cleanup-info">
                      <span>Archivos borrados: {cleanup.files_deleted}</span>
                      <span>Espacio liberado: {formatBytes(cleanup.size_freed)}</span>
                      <span>Fecha: {new Date(cleanup.started_at).toLocaleString()}</span>
                    </div>
                    
                    {cleanup.backup_path && (
                      <div className="cleanup-actions-row">
                        <span className="backup-path" title={cleanup.backup_path}>
                          Copia de seguridad: {cleanup.backup_path}
                        </span>
                        <div className="backup-buttons">
                          <button
                            className="btn-rollback"
                            onClick={() => performRollback(cleanup.operation_id, cleanup.backup_path)}
                          >
                            🔄 Restaurar Archivos
                          </button>
                          <button
                            className="btn-purge"
                            onClick={() => handleOpenPurgeModal(cleanup)}
                          >
                            🗑️ Borrar Respaldo (Liberar Espacio)
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* MiniMax AI Purge Backup Confirmation Modal */}
      {purgeModal.isOpen && (
        <div className="modal-overlay" onClick={() => setPurgeModal({ ...purgeModal, isOpen: false })}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>🔥 Confirmar Eliminación Definitiva de Respaldo</h3>
              <button className="modal-close" onClick={() => setPurgeModal({ ...purgeModal, isOpen: false })}>✕</button>
            </div>

            <div className="modal-body">
              {purgeModal.loading ? (
                <div className="modal-loading">
                  <div className="spinner"></div>
                  <p>🤖 MiniMax AI está inspeccionando los archivos dentro de la copia de respaldo...</p>
                </div>
              ) : (
                <>
                  <div className="modal-alert-banner">
                    ⚠️ <strong>AVISO IMPORTANTE:</strong> Al eliminar este respaldo se liberarán <strong>{purgeModal.backupInfo?.size_formatted || 'espacio real'}</strong> netos en tu disco, pero <u>ya no podrás deshacer esta limpieza ni usar el botón Restaurar</u>.
                  </div>

                  {purgeModal.aiAnalysis && (
                    <div className="modal-ai-box">
                      <h4>🤖 Diagnóstico del Respaldo (MiniMax AI):</h4>
                      <p className="modal-space-notice">💾 <strong>Efecto en Disco:</strong> {purgeModal.aiAnalysis.freed_space_notice}</p>
                      
                      {purgeModal.aiAnalysis.apps_and_projects_affected && purgeModal.aiAnalysis.apps_and_projects_affected.length > 0 && (
                        <div className="modal-apps-list">
                          <strong>Contenido / Aplicaciones en este respaldo:</strong>
                          <ul>
                            {purgeModal.aiAnalysis.apps_and_projects_affected.map((app, idx) => (
                              <li key={idx}>📦 {app}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <p className="modal-consequence">💡 {purgeModal.aiAnalysis.purge_consequence_es}</p>
                      <div className="modal-safety">🛡️ {purgeModal.aiAnalysis.safety_confirmation}</div>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="modal-footer">
              <button
                className="btn-modal-cancel"
                onClick={() => setPurgeModal({ ...purgeModal, isOpen: false })}
              >
                Cancelar
              </button>
              <button
                className="btn-modal-danger"
                onClick={handleConfirmPurge}
                disabled={purgeModal.loading}
              >
                🔥 Eliminar Respaldo Definitivamente ({purgeModal.backupInfo?.size_formatted || 'Liberar Espacio'})
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DiskAnalyzer;

