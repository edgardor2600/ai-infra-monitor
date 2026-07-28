import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('saas_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export const getHosts = async () => {
  const response = await api.get('/hosts');
  return response.data.hosts;
};

export const getHostMetrics = async (hostId, limit = 100) => {
  const response = await api.get(`/metrics?host_id=${hostId}&limit=${limit}`);
  return response.data;
};

export const getAlerts = async (status = 'open') => {
  const response = await api.get(`/alerts?status=${status}`);
  return response.data;
};

export const analyzeAlert = async (alertId) => {
  const response = await api.post(`/alerts/${alertId}/analyze`);
  return response.data;
};

export const getAlertAnalysis = async (alertId) => {
  try {
    const response = await api.get(`/alerts/${alertId}/analysis`);
    return response.data;
  } catch (error) {
    if (error.response?.status === 404) {
      // Analysis not ready yet, return null silently (no console error)
      return null;
    }
    // For other errors, log them
    console.error('Error fetching analysis:', error);
    throw error;
  }
};

export const updateAlertStatus = async (alertId, status) => {
  const response = await api.patch(`/alerts/${alertId}/status?status=${status}`);
  return response.data;
};

export const getTopProcesses = async (hostId, limit = 10, metric = 'cpu') => {
  const response = await api.get(`/processes/top?host_id=${hostId}&limit=${limit}&metric=${metric}`);
  return response.data;
};

export const getProcessHistory = async (processName, hostId, hours = 1) => {
  const response = await api.get(`/processes/${encodeURIComponent(processName)}/history?host_id=${hostId}&hours=${hours}`);
  return response.data;
};

export const getProcessList = async (hostId) => {
  const response = await api.get(`/processes/list?host_id=${hostId}`);
  return response.data;
};

export const getDashboardOverview = async () => {
  const response = await api.get('/dashboard/overview');
  return response.data;
};

// Disk Analyzer API endpoints
export const getDiskDrives = async () => {
  const response = await api.get('/disk-analyzer/drives');
  return response.data.drives;
};

export const startDiskScan = async (hostId = 1, drive = 'C:') => {
  const response = await api.post('/disk-analyzer/scan', { host_id: hostId, drive });
  return response.data;
};

export const getDiskScan = async (scanId) => {
  const response = await api.get(`/disk-analyzer/scan/${scanId}`);
  return response.data;
};

export const listDiskScans = async (limit = 10) => {
  const response = await api.get(`/disk-analyzer/scans?limit=${limit}`);
  return response.data;
};

export const performDiskCleanup = async (scanId, categories, createBackup = true) => {
  const response = await api.post('/disk-analyzer/cleanup', {
    scan_id: scanId,
    categories,
    create_backup: createBackup
  });
  return response.data;
};

export const analyzeScanAI = async (scanId) => {
  const response = await api.post('/disk-analyzer/analyze-ai', { scan_id: scanId });
  return response.data;
};

export const purgeBackup = async (backupPath) => {
  const response = await api.post('/disk-analyzer/purge-backup', { backup_path: backupPath });
  return response.data;
};

export const inspectBackup = async (backupPath) => {
  const response = await api.post('/disk-analyzer/inspect-backup', { backup_path: backupPath });
  return response.data;
};

export const listDiskCleanups = async (limit = 10) => {
  const response = await api.get(`/disk-analyzer/cleanups?limit=${limit}`);
  return response.data;
};

export const rollbackDiskCleanup = async (operationId) => {
  const response = await api.post('/disk-analyzer/rollback', { operation_id: operationId });
  return response.data;
};

// Super Admin Management API
export const getAdminUsers = async () => {
  const response = await api.get('/auth/admin/users');
  return response.data;
};

export const getAdminStats = async () => {
  const response = await api.get('/auth/admin/stats');
  return response.data;
};

export const changeUserTier = async (orgId, licenseTier) => {
  const response = await api.post('/auth/admin/change-tier', {
    org_id: orgId,
    license_tier: licenseTier
  });
  return response.data;
};

export const changeUserRole = async (userId, role) => {
  const response = await api.post('/auth/admin/change-role', {
    user_id: userId,
    role
  });
  return response.data;
};

export const resetUserPassword = async (userId, newPassword) => {
  const response = await api.post('/auth/admin/reset-password', {
    user_id: userId,
    new_password: newPassword
  });
  return response.data;
};

export const deleteUserAccount = async (userId) => {
  const response = await api.delete(`/auth/admin/users/${userId}`);
  return response.data;
};

export const getNotificationSettings = async () => {
  const response = await api.get('/auth/notification-settings');
  return response.data;
};

export const updateNotificationSettings = async (settings) => {
  const response = await api.post('/auth/notification-settings', settings);
  return response.data;
};

export const testWebhook = async (webhookUrl) => {
  const response = await api.post('/auth/test-webhook', { webhook_url: webhookUrl });
  return response.data;
};

export const exportScanPdf = async (scanId) => {
  const response = await api.post('/disk-analyzer/export-pdf', { scan_id: scanId, format: 'pdf' }, { responseType: 'blob' });
  return response.data;
};

export default api;

