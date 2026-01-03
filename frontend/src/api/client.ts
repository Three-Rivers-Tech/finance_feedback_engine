import axios, { AxiosError } from 'axios';
import { API_BASE_URL } from '../utils/constants';

// Normalize base URL to avoid double /api when endpoints already include the /api prefix
const normalizedBaseUrl = (() => {
  const trimmed = API_BASE_URL.replace(/\/+$/, '');
  if (trimmed.toLowerCase().endsWith('/api')) {
    return trimmed.slice(0, -4);
  }
  return trimmed;
})();

const apiClient = axios.create({
  baseURL: normalizedBaseUrl,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth header
apiClient.interceptors.request.use((config) => {
  // Try localStorage first, then environment variable
  const apiKey = localStorage.getItem('api_key') || import.meta.env.VITE_API_KEY;
  if (apiKey && config.headers) {
    config.headers.Authorization = `Bearer ${apiKey}`;
  }
  return config;
});

// Response interceptor - handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Don't reload - this causes infinite loop!
      // Instead, mark as unauthenticated and continue
      localStorage.removeItem('api_key');
      console.warn('API authentication failed - API key required or invalid');
      // Let the error propagate so components can handle gracefully
    }
    return Promise.reject(error);
  }
);

export function handleApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }
    if (error.response) {
      return `API Error: ${error.response.status}`;
    }
    if (error.request) {
      return 'Network error: API is unreachable';
    }
  }
  return 'An unexpected error occurred';
}

export default apiClient;
