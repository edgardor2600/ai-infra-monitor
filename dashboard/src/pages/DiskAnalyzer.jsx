import React, { useState, useEffect, useRef } from 'react';
import api, { inspectBackup, exportScanPdf, getNotificationSettings, updateNotificationSettings } from '../api';
import { useAuth } from '../context/AuthContext';
import DiskTreemap from '../components/DiskTreemap';
import './DiskAnalyzer.css';

const FolderSelectorUI = ({ currentPath, onPathChange, placeholder }) => {
  const fileInputRef = useRef(null);

  const handleNativeFolderPick = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const firstFile = files[0];
      const fullPath = firstFile.path;
      if (fullPath) {
        const lastSlashIndex = Math.max(fullPath.lastIndexOf('\\'), fullPath.lastIndexOf('/'));
        if (lastSlashIndex > 0) {
          onPathChange(fullPath.substring(0, lastSlashIndex));
          return;
        }
      }
      if (firstFile.webkitRelativePath) {
        const rootFolder = firstFile.webkitRelativePath.split('/')[0];
        if (rootFolder) {
          onPathChange(`C:\\${rootFolder}`);
        }
      }
    }
  };

  const presets = [
    { label: '💿 Disco C: (Raíz)', path: 'C:\\' },
    { label: '⚙️ Archivos Temporales (Windows)', path: 'C:\\Windows\\Temp' },
    { label: '📁 Archivos de Programa', path: 'C:\\Program Files' },
    { label: '🌐 Usuarios Sistema', path: 'C:\\Users' },
  ];

  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <input
        type="file"
        webkitdirectory="true"
        directory="true"
        ref={fileInputRef}
        onChange={handleNativeFolderPick}
        style={{ display: 'none' }}
      />
      <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '0.6rem' }}>
        <input
          type="text"
          className="form-input"
          style={{
            flexGrow: 1,
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            background: '#0f172a',
            color: '#f8fafc',
            fontSize: '0.95rem',
            fontFamily: 'monospace'
          }}
          value={currentPath}
          onChange={(e) => onPathChange(e.target.value)}
          placeholder={placeholder || "Selecciona o escribe la ruta de la carpeta..."}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          style={{
            padding: '0.75rem 1.25rem',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)',
            color: 'white',
            border: 'none',
            fontWeight: '700',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            boxShadow: '0 4px 12px rgba(2, 132, 199, 0.3)'
          }}
        >
          📂 Explorar Carpeta
        </button>
      </div>

      {/* Quick Preset Buttons */}
      <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: '600', marginRight: '0.2rem' }}>
          ⚡ Accesos Rápidos:
        </span>
        {presets.map((preset, pIdx) => (
          <button
            key={`preset-${pIdx}`}
            type="button"
            onClick={() => onPathChange(preset.path)}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '6px',
              background: currentPath === preset.path ? 'rgba(56, 189, 248, 0.25)' : 'rgba(255, 255, 255, 0.05)',
              border: currentPath === preset.path ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.1)',
              color: currentPath === preset.path ? '#38bdf8' : '#cbd5e1',
              fontSize: '0.82rem',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  );
};

const DiskAnalyzer = () => {
  const { user } = useAuth();
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

  // Cleanup Confirmation Modal state
  const [cleanupModal, setCleanupModal] = useState({
    isOpen: false,
    categories: [],
    totalFiles: 0,
    totalSize: 0
  });

  // Phase 4 SaaS Tabs state
  const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'duplicates', 'dev_artifacts', 'audit_logs', 'license'
  const [dupScanPath, setDupScanPath] = useState('C:\\Program Files');
  const [dupResults, setDupResults] = useState(null);
  const [dupLoading, setDupLoading] = useState(false);

  const [devScanPath, setDevScanPath] = useState('C:\\Program Files');
  const [devResults, setDevResults] = useState(null);
  const [devLoading, setDevLoading] = useState(false);

  const [auditLogs, setAuditLogs] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [purgeAlerts, setPurgeAlerts] = useState([]);

  // Phase 5 B2B License state
  const [licenseInfo, setLicenseInfo] = useState(null);
  const [licenseKeyInput, setLicenseKeyInput] = useState('');
  const [activatingLicense, setActivatingLicense] = useState(false);

  // Server Launcher Modal state
  const [showServerModal, setShowServerModal] = useState(false);
  const [downloadingLauncher, setDownloadingLauncher] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState(false);

  const handleDownloadLauncher = async (osType = 'windows') => {
    setDownloadingLauncher(true);
    try {
      const response = await api.get(`/disk-analyzer/download-launcher?os_type=${osType}`, {
        responseType: 'blob'
      });
      const ext = osType === 'windows' ? 'bat' : 'sh';
      const mimeType = osType === 'windows' ? 'application/x-bat' : 'application/x-sh';
      const blob = new Blob([response.data], { type: mimeType });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const orgId = licenseInfo?.organization_id || 1;
      link.setAttribute('download', `iniciar_servidor_org_${orgId}.${ext}`);
      document.body.appendChild(link);
      link.click();
      setTimeout(() => {
        link.remove();
        window.URL.revokeObjectURL(url);
      }, 1000);
    } catch (err) {
      console.error('Error downloading launcher:', err);
      alert('No se pudo descargar el lanzador automático.');
    } finally {
      setDownloadingLauncher(false);
    }
  };

  const handleCopyCommand = (cmdText) => {
    navigator.clipboard.writeText(cmdText);
    setCopiedCommand(true);
    setTimeout(() => setCopiedCommand(false), 2500);
  };

  const togglePreview = (categoryName) => {
    setOpenPreviews(prev => ({ ...prev, [categoryName]: !prev[categoryName] }));
  };

  useEffect(() => {
    fetchDrives();
    fetchScans();
    fetchCleanupHistory();
    fetchPurgeAlerts();
    fetchLicenseInfo();
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
      const scanList = response.data.scans || [];
      setScans(scanList);

      // Auto-load most recent completed scan for current org on page load / reload
      if (scanList.length > 0 && !currentScan) {
        const latestScan = scanList.find(s => s.status === 'completed') || scanList[0];
        const latestId = latestScan.scan_id || latestScan.id;
        if (latestId) {
          await fetchScanDetails(latestId);
        }
      }
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
      alert('No se pudo generar el análisis MiniMax AI.');
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

  const fetchAuditLogs = async () => {
    setAuditLoading(true);
    try {
      const response = await api.get('/disk-analyzer/audit-logs?limit=30');
      if (response.data.ok) {
        setAuditLogs(response.data.logs || []);
      }
    } catch (error) {
      if (error.response?.status === 403) {
        // Excluded by license tier - handled gracefully by feature gate UI
        return;
      }
      console.error('Error fetching audit logs:', error);
    } finally {
      setAuditLoading(false);
    }
  };

  const fetchPurgeAlerts = async () => {
    try {
      const response = await api.get('/disk-analyzer/backup-purge-notifications');
      if (response.data.ok) {
        setPurgeAlerts(response.data.pending_purges || []);
      }
    } catch (error) {
      console.error('Error fetching purge notifications:', error);
    }
  };

  const runDuplicateScan = async () => {
    if (!dupScanPath) return;
    setDupLoading(true);
    try {
      const response = await api.post('/disk-analyzer/scan-duplicates', {
        target_path: dupScanPath,
        min_size_mb: 1
      });
      if (response.data.ok) {
        setDupResults(response.data);
      }
    } catch (error) {
      console.error('Error scanning duplicates:', error);
      alert('Fallo al escanear duplicados o acceso denegado por nivel de licencia.');
    } finally {
      setDupLoading(false);
    }
  };

  const runDevArtifactsScan = async () => {
    if (!devScanPath) return;
    setDevLoading(true);
    try {
      const response = await api.post('/disk-analyzer/scan-dev-artifacts', {
        target_path: devScanPath
      });
      if (response.data.ok) {
        setDevResults(response.data);
      }
    } catch (error) {
      console.error('Error scanning dev artifacts:', error);
      alert('Fallo al escanear artefactos dev o acceso denegado por nivel de licencia.');
    } finally {
      setDevLoading(false);
    }
  };

  const fetchLicenseInfo = async () => {
    try {
      const response = await api.get('/disk-analyzer/license-info');
      if (response.data.ok) {
        setLicenseInfo(response.data);
      }
    } catch (error) {
      console.error('Error fetching license info:', error);
    }
  };

  const handleActivateLicense = async () => {
    if (!licenseKeyInput) return;
    setActivatingLicense(true);
    try {
      const response = await api.post('/disk-analyzer/activate-license', {
        license_key: licenseKeyInput
      });
      if (response.data.ok) {
        alert(response.data.message);
        await fetchLicenseInfo();
        setLicenseKeyInput('');
      }
    } catch (error) {
      console.error('Error activating license:', error);
      alert('Clave de licencia inválida o no reconocida.');
    } finally {
      setActivatingLicense(false);
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
      console.warn('Inspection fallback activated:', err);
      setPurgeModal(prev => ({
        ...prev,
        loading: false,
        backupInfo: {
          backup_path: cleanupItem.backup_path,
          size_formatted: formatBytes(cleanupItem.size_freed),
          categories: []
        },
        aiAnalysis: {
          title: "Inspección de Respaldo",
          freed_space_notice: `Se liberará la copia (${formatBytes(cleanupItem.size_freed)}) en tu almacenamiento.`,
          apps_and_projects_affected: [],
          purge_consequence_es: "Esta acción eliminará la copia retenida para recuperar espacio físico.",
          safety_confirmation: "Tus archivos personales y de sistema permanecen protegidos."
        }
      }));
    }
  };

  const pollTaskCompletion = async (taskId) => {
    let attempts = 0;
    const maxAttempts = 20;
    while (attempts < maxAttempts) {
      await new Promise(r => setTimeout(r, 2000));
      attempts++;
      try {
        const res = await api.get(`/disk-analyzer/task-status/${taskId}`);
        if (res.data.status === 'completed' || res.data.status === 'completed_with_warnings') {
          return res.data;
        } else if (res.data.status === 'failed') {
          throw new Error('La tarea falló en el equipo remoto.');
        }
      } catch (err) {
        if (attempts >= maxAttempts) break;
      }
    }
  };

  const handleConfirmPurge = async () => {
    if (!purgeModal.item) return;
    try {
      const response = await api.post('/disk-analyzer/purge-backup', {
        backup_path: purgeModal.item.backup_path,
        scan_id: currentScan?.scan_id
      });
      if (response.data.success || response.data.ok) {
        if (response.data.task_id) {
          await pollTaskCompletion(response.data.task_id);
        }
        setPurgeModal({ isOpen: false, item: null, loading: false, aiAnalysis: null, backupInfo: null });
        if (currentScan?.scan_id) {
          await fetchScanDetails(currentScan.scan_id);
        }
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

  const handleOpenCleanupModal = () => {
    if (selectedCategories.length === 0) {
      alert('Selecciona al menos una categoría para limpiar');
      return;
    }
    
    let totalFiles = 0;
    let totalSize = 0;
    
    selectedCategories.forEach(catKey => {
      const catData = currentScan?.categories?.[catKey];
      if (catData) {
        totalFiles += catData.file_count || 0;
        totalSize += catData.total_size || 0;
      }
    });

    setCleanupModal({
      isOpen: true,
      categories: selectedCategories,
      totalFiles,
      totalSize
    });
  };

  const handleConfirmCleanup = async () => {
    setCleanupInProgress(true);
    setCleanupModal(prev => ({ ...prev, isOpen: false }));

    try {
      const response = await api.post('/disk-analyzer/cleanup', {
        scan_id: currentScan.scan_id,
        categories: selectedCategories,
        create_backup: true
      });

      if (response.data.ok || response.data.task_id) {
        if (response.data.task_id) {
          await pollTaskCompletion(response.data.task_id);
        }
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

  // Helper renderers for Tabs
  const renderDuplicatesTab = () => {
    const isAllowed = licenseInfo?.allowed_features?.includes('sha256_duplicates');
    return (
      <div className="tab-pane card-container glass-card" style={{ background: '#131e33', border: '1px solid rgba(255, 255, 255, 0.08)', padding: '1.5rem', borderRadius: '12px', color: '#f8fafc' }}>
        <h3>🔍 Buscador de Archivos Duplicados por Hash SHA-256</h3>
        <p style={{ color: '#94a3b8' }}>Identifica archivos exactamente idénticos (mismo contenido byte a byte) para eliminar las copias redundantes reteniendo la versión maestro más reciente.</p>

        {!isAllowed ? (
          <div style={{ padding: '2rem', textAlign: 'center', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '12px', marginTop: '1.5rem' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🔒</div>
            <h3 style={{ color: '#f43f5e', margin: '0 0 0.5rem 0' }}>Función Exclusiva del Plan Pro SaaS o Enterprise B2B</h3>
            <p style={{ color: '#fda4af', maxWidth: '600px', margin: '0 auto 1.5rem auto' }}>
              El <strong>Buscador por Hash SHA-256</strong> está bloqueado bajo tu nivel de suscripción actual (<strong>{licenseInfo?.license_tier || 'STARTER'}</strong>). Para utilizar la detección exacta byte a byte, activa una licencia comercial.
            </p>
            <button
              className="btn-primary"
              onClick={() => setActiveTab('license')}
              style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', background: 'linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)', color: 'white', border: 'none', fontWeight: '700', cursor: 'pointer' }}
            >
              🔑 Ir a Activar Licencia Comercial
            </button>
          </div>
        ) : (
          <div>
            <div style={{ marginTop: '1rem', marginBottom: '1.5rem' }}>
              <FolderSelectorUI
                currentPath={dupScanPath}
                onPathChange={setDupScanPath}
                placeholder="Selecciona o escribe la carpeta a analizar por SHA-256..."
              />
              <button
                className="btn-primary"
                onClick={runDuplicateScan}
                disabled={dupLoading}
                style={{
                  width: '100%',
                  padding: '0.85rem',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
                  color: 'white',
                  border: 'none',
                  fontWeight: '700',
                  fontSize: '1rem',
                  cursor: 'pointer',
                  boxShadow: '0 4px 12px rgba(37, 99, 235, 0.35)'
                }}
              >
                {dupLoading ? 'Escaneando Hashes SHA-256...' : '🔍 Iniciar Búsqueda de Duplicados'}
              </button>
            </div>

            {dupResults && (
              <div className="dup-results">
                <div className="dup-summary" style={{ background: '#1e293b', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '1.25rem', borderRadius: '10px', marginBottom: '1.25rem', color: '#f8fafc' }}>
                  <div style={{ fontSize: '1.05rem', fontWeight: '700', color: '#38bdf8', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    ⚡ Resumen de Deduplicación SHA-256
                  </div>
                  <div style={{ color: '#cbd5e1', fontSize: '0.95rem' }}>
                    Se encontraron <strong>{dupResults.total_duplicate_files} archivos idénticos</strong> redundantes, desperdiciando un total de <strong style={{ color: '#f43f5e' }}>{formatBytes(dupResults.total_wasted_bytes)}</strong> en disco.
                  </div>
                </div>

                {dupResults.duplicate_sets?.map((dupSet, idx) => {
                  const hashStr = dupSet.sha256_hash || dupSet.sha256 || 'HASH';
                  const fileList = dupSet.files || (
                    dupSet.original_path
                      ? [{ path: dupSet.original_path, is_original: true }, ...(dupSet.duplicate_paths || []).map(p => ({ path: p, is_original: false }))]
                      : []
                  );
                  return (
                    <div key={`dup-set-${idx}`} className="dup-set-card" style={{ border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px', padding: '1rem', marginBottom: '1rem', background: '#1e293b' }}>
                      <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: '#f8fafc' }}>
                        Grupo #{idx + 1} — SHA-256: <code>{hashStr.substring(0, 16)}...</code> ({formatBytes(dupSet.file_size_bytes)} c/u)
                      </div>
                      <ul style={{ paddingLeft: '1.25rem', margin: 0 }}>
                        {fileList.map((fileItem, fIdx) => {
                          const filePath = typeof fileItem === 'string' ? fileItem : fileItem?.path;
                          const isOriginal = fIdx === 0 || fileItem?.is_original;
                          return (
                            <li key={`dup-file-${fIdx}-${filePath}`} style={{ fontSize: '0.9rem', color: isOriginal ? '#4ade80' : '#cbd5e1', fontWeight: isOriginal ? '700' : '400', marginBottom: '0.25rem' }}>
                              {isOriginal ? '⭐ [RETENER MAESTRO]: ' : '🗑️ [COPIA A BORRAR]: '}{filePath}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderDevArtifactsTab = () => {
    const effectiveTier = (user?.license_tier || licenseInfo?.license_tier || 'PRO_SAAS').toUpperCase();
    const isAllowed = effectiveTier !== 'STARTER' || licenseInfo?.allowed_features?.includes('dev_cleaner');
    return (
      <div className="tab-pane card-container glass-card" style={{ background: '#131e33', border: '1px solid rgba(255, 255, 255, 0.08)', padding: '1.5rem', borderRadius: '12px', color: '#f8fafc' }}>
        <h3>💻 Limpiador Especializado Developer & Multimedia</h3>
        <p style={{ color: '#94a3b8' }}>Detecta carpetas de compilación pesadas (<code>node_modules</code>, <code>.venv</code>, <code>.next</code>, <code>dist</code>, <code>__pycache__</code>) y caché de renderizado de Adobe Premiere/Photoshop.</p>

        {!isAllowed ? (
          <div style={{ padding: '2rem', textAlign: 'center', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '12px', marginTop: '1.5rem' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🔒</div>
            <h3 style={{ color: '#f43f5e', margin: '0 0 0.5rem 0' }}>Función Exclusiva del Plan Pro SaaS o Enterprise B2B</h3>
            <p style={{ color: '#fda4af', maxWidth: '600px', margin: '0 auto 1.5rem auto' }}>
              El <strong>Limpiador de Artefactos Dev & Media</strong> está bloqueado bajo tu nivel de suscripción actual (<strong>{licenseInfo?.license_tier || 'STARTER'}</strong>). Para utilizar la limpieza inteligente de node_modules y cachés, activa una licencia comercial.
            </p>
            <button
              className="btn-primary"
              onClick={() => setActiveTab('license')}
              style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', background: 'linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)', color: 'white', border: 'none', fontWeight: '700', cursor: 'pointer' }}
            >
              🔑 Ir a Activar Licencia Comercial
            </button>
          </div>
        ) : (
          <div>
            <div style={{ marginTop: '1rem', marginBottom: '1.5rem' }}>
              <FolderSelectorUI
                currentPath={devScanPath}
                onPathChange={setDevScanPath}
                placeholder="Selecciona o escribe la ruta base de proyectos..."
              />
              <button
                className="btn-primary"
                onClick={runDevArtifactsScan}
                disabled={devLoading}
                style={{
                  width: '100%',
                  padding: '0.85rem',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)',
                  color: 'white',
                  border: 'none',
                  fontWeight: '700',
                  fontSize: '1rem',
                  cursor: 'pointer',
                  boxShadow: '0 4px 12px rgba(2, 132, 199, 0.35)'
                }}
              >
                {devLoading ? 'Escaneando Proyectos...' : '💻 Iniciar Búsqueda de Artefactos Dev & Media'}
              </button>
            </div>

            {devResults && (
              <div className="dev-results">
                <div className="dev-summary" style={{ background: '#ecfdf5', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', color: '#065f46' }}>
                  <strong>Resumen de Proyectos:</strong> {devResults.total_artifacts} artefactos encontrados ocupando <strong>{devResults.formatted_size}</strong>.
                </div>

                <div className="artifacts-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                  {devResults.artifacts?.map((art, idx) => (
                    <div key={`dev-art-${idx}-${art.path}`} style={{ border: '1px solid #cbd5e1', borderRadius: '8px', padding: '1rem', background: '#f8fafc' }}>
                      <div style={{ fontWeight: '700', color: '#1e293b', marginBottom: '0.25rem' }}>📁 {art.type}</div>
                      <div style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#475569', marginBottom: '0.5rem' }}>{art.path}</div>
                      <div style={{ fontWeight: '600', color: '#059669' }}>{formatBytes(art.size_bytes)}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderAuditLogsTab = () => {
    const isAllowed = licenseInfo?.allowed_features?.includes('immutable_audit_logs');
    return (
      <div className="tab-pane card-container glass-card" style={{ background: '#131e33', border: '1px solid rgba(255, 255, 255, 0.08)', padding: '1.5rem', borderRadius: '12px', color: '#f8fafc' }}>
        <h3 style={{ color: '#f8fafc' }}>📜 Registro Inmutable de Auditoría Corporativa (B2B Compliance)</h3>
        <p style={{ color: '#94a3b8' }}>Logs de trazabilidad inmutables para administradores de TI: registran qué usuario ejecutó la limpieza, cuántos MB/GB liberó, en qué host y la justificación de la IA.</p>

        {!isAllowed ? (
          <div style={{ padding: '2rem', textAlign: 'center', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '12px', marginTop: '1.5rem' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🔒</div>
            <h3 style={{ color: '#f43f5e', margin: '0 0 0.5rem 0' }}>Función Exclusiva del Plan Enterprise B2B</h3>
            <p style={{ color: '#fda4af', maxWidth: '600px', margin: '0 auto 1.5rem auto' }}>
              El <strong>Registro Inmutable de Auditoría Corporativa</strong> es una característica exclusiva para cumplimiento normativo del plan <strong>Enterprise B2B</strong>. Tu plan actual es <strong>{licenseInfo?.license_tier || 'STARTER'}</strong>.
            </p>
            <button
              className="btn-primary"
              onClick={() => setActiveTab('license')}
              style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', background: '#dc2626', color: 'white', border: 'none', fontWeight: '700', cursor: 'pointer' }}
            >
              🔑 Ir a Activar Licencia Enterprise B2B
            </button>
          </div>
        ) : (
          <div>
            {auditLoading ? (
              <p style={{ color: '#94a3b8' }}>Cargando registros de auditoría...</p>
            ) : (
              <div className="audit-table-wrapper" style={{ overflowX: 'auto', marginTop: '1rem' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                  <thead>
                    <tr style={{ background: '#0f172a', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                      <th style={{ padding: '0.75rem 1rem', color: '#64748b' }}>ID</th>
                      <th style={{ padding: '0.75rem 1rem', color: '#64748b' }}>Empresa</th>
                      <th style={{ padding: '0.75rem 1rem', color: '#64748b' }}>Host</th>
                      <th style={{ padding: '0.75rem 1rem', color: '#64748b' }}>Categorías</th>
                      <th style={{ padding: '0.75rem 1rem', color: '#64748b' }}>Espacio Liberado</th>
                      <th style={{ padding: '0.75rem 1rem', color: '#64748b' }}>Proveedor IA</th>
                      <th style={{ padding: '0.75rem 1rem', color: '#64748b' }}>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log) => (
                      <tr key={`audit-log-${log.id}`} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                        <td style={{ padding: '0.75rem 1rem', fontFamily: 'JetBrains Mono, monospace' }}>#{log.id}</td>
                        <td style={{ padding: '0.75rem 1rem', fontWeight: '700', color: '#f8fafc' }}>{log.organization_name}</td>
                        <td style={{ padding: '0.75rem 1rem', color: '#94a3b8' }}>{log.hostname}</td>
                        <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1' }}>{Array.isArray(log.categories) ? log.categories.join(', ') : log.categories}</td>
                        <td style={{ padding: '0.75rem 1rem', fontWeight: '700', color: '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>{log.formatted_bytes_freed}</td>
                        <td style={{ padding: '0.75rem 1rem', color: '#38bdf8' }}>🤖 {log.ai_provider}</td>
                        <td style={{ padding: '0.75rem 1rem', color: '#64748b', fontSize: '0.8rem' }}>{new Date(log.executed_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderLicenseTab = () => {
    return (
      <div className="tab-pane card-container glass-card" style={{ background: '#131e33', border: '1px solid rgba(255, 255, 255, 0.08)', padding: '1.5rem', borderRadius: '12px', color: '#f8fafc' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, color: '#f8fafc' }}>💳 Gestión de Licencia & Planes B2B</h3>
            <p style={{ margin: '0.25rem 0 0 0', color: '#94a3b8' }}>Estado del contrato corporativo, características habilitadas y activador de claves de licencia.</p>
          </div>
          {licenseInfo && (
            <div style={{ textAlign: 'right' }}>
              <span className="status-badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.5rem 1rem', borderRadius: '20px', fontWeight: '700', fontSize: '0.85rem' }}>
                NIVEL ACTIVO: {licenseInfo.license_tier}
              </span>
            </div>
          )}
        </div>

        {/* Current License Card */}
        {licenseInfo && (
          <div style={{ background: '#0f172a', border: '1px solid rgba(255, 255, 255, 0.08)', color: 'white', padding: '1.5rem', borderRadius: '12px', marginBottom: '2rem', boxShadow: '0 10px 25px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem' }}>
              <div>
                <div style={{ color: '#64748b', fontSize: '0.8rem', textTransform: 'uppercase', fontWeight: '600' }}>Organización Suscriptora:</div>
                <div style={{ fontSize: '1.2rem', fontWeight: '700', marginTop: '0.25rem', color: '#f8fafc' }}>🏢 {licenseInfo.organization_name}</div>
              </div>
              <div>
                <div style={{ color: '#64748b', fontSize: '0.8rem', textTransform: 'uppercase', fontWeight: '600' }}>Proveedor de IA Configurado:</div>
                <div style={{ fontSize: '1.2rem', fontWeight: '700', marginTop: '0.25rem', color: '#38bdf8' }}>🤖 {licenseInfo.active_llm_provider}</div>
              </div>
              <div>
                <div style={{ color: '#64748b', fontSize: '0.8rem', textTransform: 'uppercase', fontWeight: '600' }}>Límite de Hosts Monitoreados:</div>
                <div style={{ fontSize: '1.2rem', fontWeight: '700', marginTop: '0.25rem', color: '#10b981' }}>🖥️ Hasta {licenseInfo.max_hosts} equipos</div>
              </div>
            </div>
          </div>
        )}

        {/* License Key Activation Row */}
        <div style={{ background: '#0f172a', border: '1px solid rgba(255, 255, 255, 0.08)', padding: '1.25rem', borderRadius: '10px', marginBottom: '2rem' }}>
          <h4 style={{ margin: '0 0 0.5rem 0', color: '#f8fafc' }}>🔑 Activar Clave de Licencia B2B</h4>
          <p style={{ margin: '0 0 1rem 0', fontSize: '0.85rem', color: '#94a3b8' }}>Ingresa tu código de licencia corporativa o clave promocional (Ej. <code>ENTERPRISE-KEY-2026</code> o <code>PRO-SAAS-KEY</code>).</p>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <input
              type="text"
              className="form-input"
              style={{ flexGrow: 1, padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.12)', background: '#131e33', color: '#f8fafc', textTransform: 'uppercase', fontFamily: 'JetBrains Mono, monospace' }}
              value={licenseKeyInput}
              onChange={(e) => setLicenseKeyInput(e.target.value)}
              placeholder="Ingresa clave de licencia B2B (Ej: ENTERPRISE-KEY-2026)"
            />
            <button
              className="btn-primary"
              onClick={handleActivateLicense}
              disabled={activatingLicense || !licenseKeyInput}
              style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', background: 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)', color: 'white', border: 'none', fontWeight: '700', cursor: 'pointer' }}
            >
              {activatingLicense ? 'Validando...' : '🔑 Activar Licencia'}
            </button>
          </div>
        </div>

        {/* Plans Comparison Grid */}
        <h4 style={{ margin: '0 0 1rem 0', color: '#f8fafc' }}>💎 Comparativa de Planes Comerciales</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
          {/* Starter Plan */}
          <div style={{ border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '1.5rem', background: '#0f172a' }}>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#cbd5e1' }}>🥉 Starter / Gratuito</div>
            <div style={{ fontSize: '1.6rem', fontWeight: '800', margin: '0.5rem 0', color: '#f8fafc', fontFamily: 'JetBrains Mono, monospace' }}>$0 <span style={{ fontSize: '0.85rem', fontWeight: '400', color: '#64748b' }}>/siempre</span></div>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Para usuarios individuales que buscan un análisis de disco rápido manual.</p>
            <ul style={{ paddingLeft: '1.25rem', fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.8' }}>
              <li>✓ Escaneo profundo de unidades local</li>
              <li>✓ Limpieza manual de archivos temporales</li>
              <li>❌ Buscador por Hash SHA-256</li>
              <li>❌ Limpiador de Proyectos Dev/Media</li>
              <li>❌ Historial inmutable de Auditoría B2B</li>
            </ul>
          </div>

          {/* Pro SaaS Plan */}
          <div style={{ border: '1px solid rgba(56, 189, 248, 0.4)', borderRadius: '12px', padding: '1.5rem', background: 'rgba(56, 189, 248, 0.06)', position: 'relative', boxShadow: '0 0 20px rgba(56, 189, 248, 0.1)' }}>
            <span style={{ position: 'absolute', top: '-12px', right: '20px', background: '#38bdf8', color: '#080c14', padding: '0.2rem 0.6rem', borderRadius: '12px', fontSize: '0.72rem', fontWeight: '800', letterSpacing: '0.05em' }}>RECOMENDADO</span>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#38bdf8' }}>🥈 Pro SaaS Edition</div>
            <div style={{ fontSize: '1.6rem', fontWeight: '800', margin: '0.5rem 0', color: '#f8fafc', fontFamily: 'JetBrains Mono, monospace' }}>$29 <span style={{ fontSize: '0.85rem', fontWeight: '400', color: '#94a3b8' }}>/mes por equipo</span></div>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Para profesionales, freelancers y desarrolladores de software.</p>
            <ul style={{ paddingLeft: '1.25rem', fontSize: '0.85rem', color: '#7dd3fc', lineHeight: '1.8' }}>
              <li>✓ Todo lo del plan Starter</li>
              <li>✓ Buscador por Hash SHA-256 (Duplicados)</li>
              <li>✓ Limpiador Dev & Media (node_modules, Adobe)</li>
              <li>✓ Mapa Treemap visual interactivo</li>
              <li>✓ Exportador de Informes Corporativos JSON</li>
              <li>✓ Asistente inteligente MiniMax AI</li>
            </ul>
          </div>

          {/* Enterprise B2B Plan */}
          <div style={{ border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: '12px', padding: '1.5rem', background: 'rgba(192, 132, 252, 0.06)', boxShadow: '0 0 20px rgba(192, 132, 252, 0.1)' }}>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#c084fc' }}>🥇 Enterprise B2B</div>
            <div style={{ fontSize: '1.6rem', fontWeight: '800', margin: '0.5rem 0', color: '#f8fafc', fontFamily: 'JetBrains Mono, monospace' }}>Personalizado</div>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Para empresas y departamentos de TI con cumplimiento normativo.</p>
            <ul style={{ paddingLeft: '1.25rem', fontSize: '0.85rem', color: '#e9d5ff', lineHeight: '1.8' }}>
              <li>✓ Todo lo del plan Pro SaaS</li>
              <li>✓ Registro Inmutable de Auditoría B2B Compliance</li>
              <li>✓ Multi-tenant para cientos de organizaciones</li>
              <li>✓ Modo Air-gapped 100% Offline (Sin nube)</li>
              <li>✓ Proveedor LLM Configurable (Gemini/Ollama/MiniMax)</li>
            </ul>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="disk-analyzer">
      <div className="disk-analyzer-header">
        <h1>Análisis y Limpieza Inteligente de Disco (MiniMax AI)</h1>
        <p className="subtitle">Escaneo profundo, 100% seguro y optimización de almacenamiento</p>
      </div>

      {/* Purge Alert Notifications Banner */}
      {purgeAlerts.length > 0 && (
        <div className="purge-warning-banner" style={{ background: '#fffbebf0', borderLeft: '4px solid #f59e0b', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', color: '#92400e' }}>
          ⚠️ <strong>Aviso de Auto-Purga de Respaldos:</strong> Tienes {purgeAlerts.length} copias de seguridad de más de 25 días. Se purgarán automáticamente a los 30 días para conservar almacenamiento disponible continuo.
        </div>
      )}

      {/* Phase 4 SaaS Tabs Navigation */}
      <div className="saas-nav-tabs" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '0.5rem', flexWrap: 'wrap' }}>
        <button
          className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
          style={{
            padding: '0.65rem 1.25rem',
            border: activeTab === 'overview' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
            fontWeight: '600',
            cursor: 'pointer',
            background: activeTab === 'overview' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'overview' ? '#38bdf8' : '#94a3b8',
            transition: 'all 0.2s ease'
          }}
        >
          📊 Visión General & Limpieza
        </button>
        <button
          className={`tab-btn ${activeTab === 'duplicates' ? 'active' : ''}`}
          onClick={() => setActiveTab('duplicates')}
          style={{
            padding: '0.65rem 1.25rem',
            border: activeTab === 'duplicates' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
            fontWeight: '600',
            cursor: 'pointer',
            background: activeTab === 'duplicates' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'duplicates' ? '#38bdf8' : '#94a3b8',
            transition: 'all 0.2s ease'
          }}
        >
          🔍 Buscador de Duplicados (SHA-256) {licenseInfo && !licenseInfo.allowed_features?.includes('sha256_duplicates') && '🔒'}
        </button>
        <button
          className={`tab-btn ${activeTab === 'dev_artifacts' ? 'active' : ''}`}
          onClick={() => setActiveTab('dev_artifacts')}
          style={{
            padding: '0.65rem 1.25rem',
            border: activeTab === 'dev_artifacts' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
            fontWeight: '600',
            cursor: 'pointer',
            background: activeTab === 'dev_artifacts' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'dev_artifacts' ? '#38bdf8' : '#94a3b8',
            transition: 'all 0.2s ease'
          }}
        >
          💻 Artefactos Dev & Media {licenseInfo && !licenseInfo.allowed_features?.includes('dev_cleaner') && '🔒'}
        </button>
        <button
          className={`tab-btn ${activeTab === 'audit_logs' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('audit_logs');
            if (licenseInfo?.allowed_features?.includes('immutable_audit_logs')) {
              fetchAuditLogs();
            }
          }}
          style={{
            padding: '0.65rem 1.25rem',
            border: activeTab === 'audit_logs' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
            fontWeight: '600',
            cursor: 'pointer',
            background: activeTab === 'audit_logs' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'audit_logs' ? '#38bdf8' : '#94a3b8',
            transition: 'all 0.2s ease'
          }}
        >
          📜 Auditoría B2B ({auditLogs.length}) {licenseInfo && !licenseInfo.allowed_features?.includes('immutable_audit_logs') && '🔒'}
        </button>
        <button
          className={`tab-btn ${activeTab === 'license' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('license');
            fetchLicenseInfo();
          }}
          style={{
            padding: '0.65rem 1.25rem',
            border: activeTab === 'license' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
            fontWeight: '600',
            cursor: 'pointer',
            background: activeTab === 'license' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'license' ? '#38bdf8' : '#94a3b8',
            transition: 'all 0.2s ease'
          }}
        >
          💳 Licencia & Planes B2B
        </button>
      </div>

      {/* Tab 1: Visión General & Limpieza */}
      {activeTab === 'overview' && (
        <>
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
                  drives.map(drive => (
                    <option key={`drive-opt-${drive.drive}`} value={drive.drive}>
                      {drive.drive} ({drive.percent_used}% usado - {formatBytes(drive.free_bytes)} libres)
                    </option>
                  ))
                ) : (
                  <option value="C:">C:</option>
                )}
              </select>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <button
                className="btn-scan"
                onClick={startScan}
                disabled={loading || scanning}
              >
                {scanning ? 'Escaneando Disco...' : 'Iniciar Escaneo Completo'}
              </button>

              <button
                type="button"
                onClick={() => setShowServerModal(true)}
                style={{
                  background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                  color: '#ffffff',
                  border: 'none',
                  padding: '0.75rem 1.25rem',
                  borderRadius: '8px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)'
                }}
              >
                ⚡ Iniciar Servidor Local (.bat)
              </button>
            </div>
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
                      <span className="disk-value">{formatBytes(currentScan.disk_info.total || 0)}</span>
                    </div>
                    <div className="disk-stat">
                      <span className="disk-label">Usado</span>
                      <span className="disk-value">{formatBytes(currentScan.disk_info.used || 0)}</span>
                    </div>
                    <div className="disk-stat">
                      <span className="disk-label">Libre</span>
                      <span className="disk-value free">{formatBytes(currentScan.disk_info.free || 0)}</span>
                    </div>
                  </div>
                  <div className="disk-progress-bar">
                    <div
                      className="disk-progress-fill"
                      style={{ width: `${currentScan.disk_info.percent_used ?? currentScan.disk_info.used_percent ?? 0}%` }}
                    ></div>
                  </div>
                  <div className="disk-progress-label">
                    {currentScan.disk_info.percent_used ?? currentScan.disk_info.used_percent ?? 0}% Usado
                  </div>
                </div>
              )}

              {currentScan.status === 'completed' && (
                <div className="ai-section">
                  <div className="ai-actions-row" style={{ display: 'flex', gap: '1rem' }}>
                    <button 
                      className="btn-ai-analyze" 
                      onClick={requestAIAnalysis}
                      disabled={aiLoading}
                    >
                      {aiLoading ? 'Generando Informe MiniMax AI...' : '🤖 Analizar con MiniMax AI'}
                    </button>

                    <button 
                      className="btn-export-report" 
                      style={{ background: '#3b82f6', color: 'white', border: 'none', padding: '0.75rem 1.5rem', borderRadius: '8px', fontWeight: '600', cursor: 'pointer' }}
                      onClick={async () => {
                        try {
                          const res = await api.post('/disk-analyzer/export-report', { scan_id: currentScan.scan_id, format: 'json' });
                          if (res.data.ok) {
                            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(res.data.report_data, null, 2));
                            const dlAnchor = document.createElement('a');
                            dlAnchor.setAttribute("href", dataStr);
                            dlAnchor.setAttribute("download", `informe_corporativo_disco_scan_${currentScan.scan_id}.json`);
                            document.body.appendChild(dlAnchor);
                            dlAnchor.click();
                            dlAnchor.remove();
                          }
                        } catch (e) {
                          alert('No se pudo exportar el informe o requiere plan Pro SaaS.');
                        }
                      }}
                    >
                      📄 Exportar Informe Corporativo (JSON)
                    </button>

                    <button 
                      className="btn-export-pdf" 
                      style={{ background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)', color: 'white', border: 'none', padding: '0.75rem 1.5rem', borderRadius: '8px', fontWeight: '600', cursor: 'pointer' }}
                      onClick={async () => {
                        try {
                          const scanId = currentScan.scan_id || currentScan.id;
                          const blobData = await exportScanPdf(scanId);
                          const url = window.URL.createObjectURL(new Blob([blobData]));
                          const link = document.createElement('a');
                          link.href = url;
                          link.setAttribute('download', `Informe_Corporativo_Scan_${scanId}.pdf`);
                          document.body.appendChild(link);
                          link.click();
                          link.remove();
                        } catch (e) {
                          alert('No se pudo exportar el informe en PDF.');
                        }
                      }}
                    >
                      📄 Exportar Informe Corporativo (PDF)
                    </button>
                  </div>

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
                              <li key={`rec-${i}`}>{rec}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Phase 3: Interactive Treemap Component */}
              {currentScan.status === 'completed' && currentScan.categories && (
                <DiskTreemap
                  categories={currentScan.categories}
                  selectedCategories={selectedCategories}
                  onSelectCategory={toggleCategory}
                />
              )}

              {currentScan.status === 'completed' && currentScan.categories && (
                <div key={`scan-container-${currentScan.scan_id}`}>
                  {(() => {
                    const validCategories = Object.entries(currentScan.categories).filter(
                      ([key, data]) => key !== 'disk_info' && key !== 'drive' && data.file_count > 0
                    );

                    return validCategories.length > 0 ? (
                      <div className="categories-section" key="cats-wrapper-block">
                        <div className="categories-grid">
                          {validCategories.map(([categoryName, categoryData]) => (
                            <div
                              key={`cat-card-${categoryName}`}
                              className={`category-card ${selectedCategories.includes(categoryName) ? 'selected' : ''}`}
                              onClick={() => toggleCategory(categoryName)}
                            >
                              <div className="category-header">
                                <input
                                  type="checkbox"
                                  checked={selectedCategories.includes(categoryName)}
                                  onChange={() => {}}
                                  onClick={(e) => e.stopPropagation()}
                                />
                                <h3>{categoryData.display_name || categoryName}</h3>
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

                              {categoryData.safe_for_auto_clean && (
                                <div className="safe-badge">
                                  ✓ Seguro para limpieza automática
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
                                        <div key={`cat-file-${categoryName}-${idx}-${file.path}`} className="file-item">
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
                            onClick={handleOpenCleanupModal}
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
                    <div key={`cleanup-item-${cleanup.operation_id}`} className="cleanup-item">
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
                              {cleanup.backup_exists ? (
                                <>
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
                                </>
                              ) : (
                                <span className="badge-purged" style={{ background: '#e2e8f0', color: '#475569', padding: '0.4rem 0.8rem', borderRadius: '6px', fontSize: '0.85rem', fontWeight: '600' }}>
                                  ✅ Respaldo Ya Purgado (Espacio Liberado)
                                </span>
                              )}
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
        </>
      )}

      {/* Tab 2: Buscador de Duplicados por SHA-256 */}
      {activeTab === 'duplicates' && renderDuplicatesTab()}

      {/* Tab 3: Artefactos Dev & Multimedia */}
      {activeTab === 'dev_artifacts' && renderDevArtifactsTab()}

      {/* Tab 4: Registro Corporativo de Auditoría B2B */}
      {activeTab === 'audit_logs' && renderAuditLogsTab()}

      {/* Tab 5: Licencia & Planes B2B */}
      {activeTab === 'license' && renderLicenseTab()}

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
                      <h4>🤖 Diagnóstico MiniMax AI sobre este Respaldo:</h4>
                      <p className="modal-ai-summary">{purgeModal.aiAnalysis.purge_consequence_es}</p>
                      <div className="modal-safety-tag">🛡️ {purgeModal.aiAnalysis.safety_confirmation}</div>
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
                🗑️ Eliminar Copia de Seguridad Definitivamente
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Zero-Risk Cleanup Confirmation Modal */}
      {cleanupModal.isOpen && (
        <div className="modal-overlay" onClick={() => setCleanupModal({ ...cleanupModal, isOpen: false })}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>🧹 Confirmar Limpieza de Disco</h3>
              <button className="modal-close" onClick={() => setCleanupModal({ ...cleanupModal, isOpen: false })}>✕</button>
            </div>

            <div className="modal-body">
              <div className="modal-success-banner">
                🛡️ <strong>Garantía de Cero Riesgo:</strong> Todos los archivos se moverán primero a una copia de respaldo encriptada. Podrás restaurarlos con 1 solo clic en cualquier momento.
              </div>

              <div className="modal-stats-pills">
                <div className="modal-stat-pill">
                  <span className="pill-label">Categorías:</span>
                  <span className="pill-val">{cleanupModal.categories.length}</span>
                </div>
                <div className="modal-stat-pill">
                  <span className="pill-label">Archivos a limpiar:</span>
                  <span className="pill-val">{cleanupModal.totalFiles}</span>
                </div>
                <div className="modal-stat-pill highlight">
                  <span className="pill-label">Espacio a liberar:</span>
                  <span className="pill-val">{formatBytes(cleanupModal.totalSize)}</span>
                </div>
              </div>

              <div className="modal-categories-list">
                <h4>Categorías a procesar:</h4>
                <ul>
                  {cleanupModal.categories.map((catKey) => {
                    const catData = currentScan?.categories?.[catKey];
                    return (
                      <li key={`modal-cat-${catKey}`}>
                        ✓ <strong>{catData?.display_name || catKey}</strong> ({formatBytes(catData?.total_size)})
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="btn-modal-cancel"
                onClick={() => setCleanupModal({ ...cleanupModal, isOpen: false })}
              >
                Cancelar
              </button>
              <button
                className="btn-modal-success"
                onClick={handleConfirmCleanup}
                disabled={cleanupInProgress}
              >
                {cleanupInProgress ? 'Limpiando...' : `✅ Iniciar Limpieza (${formatBytes(cleanupModal.totalSize)})`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Server Launcher / Connection Modal */}
      {showServerModal && (
        <div className="modal-overlay" onClick={() => setShowServerModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '650px', background: '#0f172a', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '16px', padding: '1.75rem', color: '#f8fafc' }}>
            <div className="purge-modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '1.75rem' }}>🚀</span>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#f8fafc', fontWeight: 700 }}>Conectar Servidor de Monitoreo Local</h3>
                  <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>Vincula tu computadora en 1 clic descargando el script ejecutable para tu cuenta.</p>
                </div>
              </div>
              <button 
                onClick={() => setShowServerModal(false)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.5rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginBottom: '1.5rem' }}>
              {/* Option 1: 1-Click BAT Launcher Download */}
              <div style={{ background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(79, 70, 229, 0.1) 100%)', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '12px', padding: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ margin: 0, color: '#818cf8', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
                    <span>💻</span> Opción 1: Lanzador Automático (Windows .bat)
                  </h4>
                  <span style={{ background: '#4f46e5', color: 'white', padding: '0.2rem 0.6rem', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600 }}>Recomendado</span>
                </div>
                <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                  Descarga el archivo <code>.bat</code> personalizado para tu organización (ID: {licenseInfo?.organization_id || 1}). Solo debes hacerle <strong>doble clic en tu equipo</strong> para encender el servidor de monitoreo.
                </p>

                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => handleDownloadLauncher('windows')}
                    disabled={downloadingLauncher}
                    style={{
                      background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                      color: 'white',
                      border: 'none',
                      padding: '0.75rem 1.25rem',
                      borderRadius: '8px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      fontSize: '0.9rem'
                    }}
                  >
                    📥 {downloadingLauncher ? 'Generando Lanzador...' : 'Descargar Lanzador (.bat)'}
                  </button>

                  <button
                    onClick={() => handleDownloadLauncher('bash')}
                    disabled={downloadingLauncher}
                    style={{
                      background: 'rgba(255, 255, 255, 0.08)',
                      color: '#e2e8f0',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      padding: '0.75rem 1rem',
                      borderRadius: '8px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontSize: '0.85rem'
                    }}
                  >
                    🐧 Descargar para Linux / macOS (.sh)
                  </button>
                </div>
              </div>

              {/* Instructions steps */}
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '1rem' }}>
                <h4 style={{ margin: '0 0 0.75rem 0', color: '#38bdf8', fontSize: '0.9rem' }}>📋 Pasos sencillos:</h4>
                <ol style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.85rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  <li>Haz clic en <strong>Descargar Lanzador (.bat)</strong> para guardar el ejecutable.</li>
                  <li>Ve a tu carpeta de descargas o escritorio y haz <strong>doble clic</strong> sobre el archivo <code>iniciar_servidor_org_{licenseInfo?.organization_id || 1}.bat</code>.</li>
                  <li>Se abrirá la consola de comandos activando la telemetría y el limpiador en vivo en tu cuenta.</li>
                </ol>
              </div>

              {/* Option 2: Copy CLI command */}
              <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '1rem' }}>
                <h4 style={{ margin: '0 0 0.5rem 0', color: '#94a3b8', fontSize: '0.875rem' }}>⌨️ Opción 2: Comando CLI para Consola CMD</h4>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    readOnly
                    value={`set BACKEND_URL=https://ai-infra-monitor-api.onrender.com && set AGENT_ORG_ID=${licenseInfo?.organization_id || 1} && python -c "import urllib.request; urllib.request.urlretrieve('https://ai-infra-monitor-api.onrender.com/agent/standalone_agent.py', 'standalone_agent.py')" && python standalone_agent.py`}
                    style={{ flexGrow: 1, padding: '0.5rem 0.75rem', background: '#020617', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', color: '#38bdf8', fontFamily: 'monospace', fontSize: '0.75rem' }}
                  />
                  <button
                    onClick={() => handleCopyCommand(`set BACKEND_URL=https://ai-infra-monitor-api.onrender.com && set AGENT_ORG_ID=${licenseInfo?.organization_id || 1} && python -c "import urllib.request; urllib.request.urlretrieve('https://ai-infra-monitor-api.onrender.com/agent/standalone_agent.py', 'standalone_agent.py')" && python standalone_agent.py`)}
                    style={{ padding: '0.5rem 1rem', background: copiedCommand ? '#10b981' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem' }}
                  >
                    {copiedCommand ? '✓ ¡Copiado!' : '📋 Copiar'}
                  </button>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowServerModal(false)}
                style={{ padding: '0.6rem 1.25rem', background: 'rgba(255, 255, 255, 0.1)', color: '#e2e8f0', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DiskAnalyzer;
