import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getHosts = async () => {
  const response = await api.get('/hosts');
  return response.data;
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

export default api;
