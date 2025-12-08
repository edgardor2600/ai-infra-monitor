import React, { useState, useEffect } from 'react';
import api from '../api';
import './DiskAnalyzer.css';

const DiskAnalyzer = () => {
  const [scans, setScans] = useState([]);
  const [currentScan, setCurrentScan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [cleanupInProgress, setCleanupInProgress] = useState(false);
  const [cleanupHistory, setCleanupHistory] = useState([]);
  const [showCleanupHistory, setShowCleanupHistory] = useState(false);

  // Fetch scans on component mount
  useEffect(() => {
    fetchScans();
    fetchCleanupHistory();
  }, []);

  // Poll for scan updates when scanning
  useEffect(() => {
    if (scanning && currentScan) {
      const interval = setInterval(() => {
        fetchScanDetails(currentScan.scan_id);
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(interval);
    }
  }, [scanning, currentScan]);

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
      
      // Stop polling if scan is completed or failed
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
    
    try {
      // Get first host (or you can add host selection)
      const hostsResponse = await api.get('/hosts');
      const hosts = hostsResponse.data.hosts || [];
      
      if (hosts.length === 0) {
        alert('No hosts found. Please ensure the agent is running.');
        setLoading(false);
        setScanning(false);
        return;
      }

      const hostId = hosts[0].id;
      
      const response = await api.post('/disk-analyzer/scan', {
        host_id: hostId
      });

      if (response.data.ok) {
        const scanId = response.data.scan_id;
        
        // Fetch scan details
        await fetchScanDetails(scanId);
        await fetchScans();
      }
    } catch (error) {
      console.error('Error starting scan:', error);
      alert('Failed to start scan. Please try again.');
      setScanning(false);
    } finally {
      setLoading(false);
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

  const performRollback = async (operationId, backupPath) => {
    const confirmRollback = window.confirm(
      `Are you sure you want to restore files from this backup?\n\n` +
      `Backup location: ${backupPath}\n\n` +
      `This will restore all files that were deleted in this cleanup operation.`
    );

    if (!confirmRollback) {
      return;
    }

    try {
      const response = await api.post('/disk-analyzer/rollback', {
        operation_id: operationId
      });

      if (response.data.ok) {
        alert(
          `Rollback completed successfully!\n\n` +
          `Files restored: ${response.data.files_restored}`
        );
        
        // Refresh cleanup history
        await fetchCleanupHistory();
      }
    } catch (error) {
      console.error('Error performing rollback:', error);
      alert('Failed to perform rollback. Please check the logs.');
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
      alert('Please select at least one category to clean');
      return;
    }

    const confirmCleanup = window.confirm(
      `Are you sure you want to clean ${selectedCategories.length} categories?\n\n` +
      `Selected categories:\n${selectedCategories.join(', ')}\n\n` +
      `A backup will be created before deletion.`
    );

    if (!confirmCleanup) {
      return;
    }

    setCleanupInProgress(true);

    try {
      const response = await api.post('/disk-analyzer/cleanup', {
        scan_id: currentScan.scan_id,
        categories: selectedCategories,
        create_backup: true
      });

      if (response.data.ok) {
        alert(
          `Cleanup completed successfully!\n\n` +
          `Files deleted: ${response.data.files_deleted}\n` +
          `Space freed: ${formatBytes(response.data.size_freed)}\n` +
          `Backup location: ${response.data.backup_path}`
        );

        // Refresh the scan to show updated data
        await fetchScanDetails(currentScan.scan_id);
        
        // Also refresh the scans list
        await fetchScans();
        
        // Refresh cleanup history
        await fetchCleanupHistory();
        
        // Clear selections
        setSelectedCategories([]);
      }
    } catch (error) {
      console.error('Error performing cleanup:', error);
      alert('Failed to perform cleanup. Please try again.');
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
        <h1>Disk Analyzer</h1>
        <p className="subtitle">Analyze and clean up disk space safely</p>
      </div>

      <div className="actions-section">
        <button
          className="btn-primary"
          onClick={startScan}
          disabled={loading || scanning}
        >
          {scanning ? 'Scanning...' : 'Start New Scan'}
        </button>
      </div>

      {currentScan && (
        <div className="scan-results">
          <div className="scan-header">
            <h2>Scan Results</h2>
            <div className="scan-status">
              <span className={`status-badge status-${currentScan.status}`}>
                {currentScan.status}
              </span>
              {currentScan.total_size && (
                <span className="total-size">
                  Total recoverable: {formatBytes(currentScan.total_size)}
                </span>
              )}
            </div>
          </div>

          {/* Disk Space Widget */}
          {currentScan.disk_info && (
            <div className="disk-space-widget">
              <h3>💾 Disk Space (C:)</h3>
              <div className="disk-stats">
                <div className="disk-stat">
                  <span className="disk-label">Total</span>
                  <span className="disk-value">{formatBytes(currentScan.disk_info.total)}</span>
                </div>
                <div className="disk-stat">
                  <span className="disk-label">Used</span>
                  <span className="disk-value">{formatBytes(currentScan.disk_info.used)}</span>
                </div>
                <div className="disk-stat">
                  <span className="disk-label">Free</span>
                  <span className="disk-value free">{formatBytes(currentScan.disk_info.free)}</span>
                </div>
              </div>
              <div className="disk-progress-bar">
                <div 
                  className="disk-progress-fill"
                  style={{ width: `${currentScan.disk_info.used_percent}%` }}
                >
                  <span className="disk-progress-text">{currentScan.disk_info.used_percent}% Used</span>
                </div>
              </div>
            </div>
          )}

          {currentScan.status === 'completed' && currentScan.categories && (() => {
            // Filter out empty categories and disk_info
            const categoriesWithFiles = Object.entries(currentScan.categories)
              .filter(([categoryName, categoryData]) => 
                categoryName !== 'disk_info' && 
                categoryData.file_count > 0
              );
            
            return categoriesWithFiles.length > 0 ? (
              <>
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
                        <span className="stat-label">Files:</span>
                        <span className="stat-value">{categoryData.file_count}</span>
                      </div>
                      <div className="stat">
                        <span className="stat-label">Size:</span>
                        <span className="stat-value">{formatBytes(categoryData.total_size)}</span>
                      </div>
                    </div>

                    {categoryData.is_safe_auto && (
                      <div className="safe-badge">
                        ✓ Safe for automatic cleanup
                      </div>
                    )}

                    {/* File Preview Section */}
                    {categoryData.files && categoryData.files.length > 0 && (
                      <details className="file-preview">
                        <summary>
                          View sample files ({Math.min(5, categoryData.files.length)} of {categoryData.file_count})
                        </summary>
                        <div className="file-list">
                          {categoryData.files.slice(0, 5).map((file, idx) => (
                            <div key={idx} className="file-item">
                              <div className="file-path" title={file.path}>
                                {file.path.length > 60 
                                  ? '...' + file.path.slice(-60) 
                                  : file.path}
                              </div>
                              <div className="file-size">{formatBytes(file.size)}</div>
                            </div>
                          ))}
                          {categoryData.file_count > 5 && (
                            <div className="file-item more-files">
                              ... and {categoryData.file_count - 5} more files
                            </div>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                ))}
              </div>

              <div className="cleanup-actions">
                <div className="selected-info">
                  {selectedCategories.length > 0 ? (
                    <p>
                      <strong>{selectedCategories.length}</strong> categories selected
                    </p>
                  ) : (
                    <p>Select categories to clean</p>
                  )}
                </div>
                <button
                  className="btn-cleanup"
                  onClick={performCleanup}
                  disabled={selectedCategories.length === 0 || cleanupInProgress}
                >
                  {cleanupInProgress ? 'Cleaning...' : 'Clean Selected'}
                </button>
              </div>
            </>
            ) : (
              <div className="all-clean-message">
                <div className="success-icon">✨</div>
                <h3>All Clean!</h3>
                <p>No cleanup items found. Your disk is already optimized!</p>
              </div>
            );
          })()}

          {currentScan.status === 'running' && (
            <div className="scanning-indicator">
              <div className="spinner"></div>
              <p>Scanning disk... This may take a few minutes.</p>
            </div>
          )}

          {currentScan.status === 'failed' && (
            <div className="error-message">
              <p>Scan failed: {currentScan.error_message}</p>
            </div>
          )}
        </div>
      )}

      {scans.length > 0 && (
        <div className="scan-history">
          <h2>Scan History</h2>
          <div className="scans-list">
            {scans.map((scan) => (
              <div
                key={scan.scan_id}
                className="scan-item"
                onClick={() => fetchScanDetails(scan.scan_id)}
              >
                <div className="scan-item-header">
                  <span className="scan-id">Scan #{scan.scan_id}</span>
                  <span className={`status-badge status-${scan.status}`}>
                    {scan.status}
                  </span>
                </div>
                <div className="scan-item-details">
                  <span>Started: {new Date(scan.started_at).toLocaleString()}</span>
                  {scan.total_size && (
                    <span>Recoverable: {formatBytes(scan.total_size)}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {cleanupHistory.length > 0 && (
        <div className="cleanup-history">
          <div className="history-header">
            <h2>Cleanup History</h2>
            <button 
              className="btn-toggle-history"
              onClick={() => setShowCleanupHistory(!showCleanupHistory)}
            >
              {showCleanupHistory ? 'Hide' : 'Show'} History
            </button>
          </div>
          
          {showCleanupHistory && (
            <div className="cleanup-list">
              {cleanupHistory.map((cleanup) => (
                <div key={cleanup.operation_id} className="cleanup-item">
                  <div className="cleanup-item-header">
                    <span className="cleanup-id">Cleanup #{cleanup.operation_id}</span>
                    <span className={`status-badge status-${cleanup.status}`}>
                      {cleanup.status}
                    </span>
                  </div>
                  
                  <div className="cleanup-item-details">
                    <div className="cleanup-info">
                      <span>Scan: #{cleanup.scan_id}</span>
                      <span>Files deleted: {cleanup.files_deleted}</span>
                      <span>Space freed: {formatBytes(cleanup.size_freed)}</span>
                      <span>Date: {new Date(cleanup.started_at).toLocaleString()}</span>
                    </div>
                    
                    <div className="cleanup-categories">
                      <strong>Categories:</strong> {cleanup.categories_cleaned?.join(', ')}
                    </div>
                    
                    {cleanup.backup_path && (
                      <div className="cleanup-actions-row">
                        <span className="backup-path" title={cleanup.backup_path}>
                          Backup: {cleanup.backup_path}
                        </span>
                        <button
                          className="btn-rollback"
                          onClick={() => performRollback(cleanup.operation_id, cleanup.backup_path)}
                        >
                          🔄 Restore Files
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DiskAnalyzer;
