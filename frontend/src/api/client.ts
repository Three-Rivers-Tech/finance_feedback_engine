import axios, { AxiosError } from 'axios';
import { API_BASE_URL } from '../utils/constants';
import { clearStoredApiKey, getEffectiveApiKey } from '../utils/auth';

// Normalize base URL to avoid double /api when endpoints already include the /api prefix
const normalizedBaseUrl = (() => {
  const trimmed = API_BASE_URL.replace(/\/+$/, '');

  // Only strip trailing /api for absolute URLs to avoid removing the
  // relative /api proxy path used in production nginx.
  const isAbsolute = /^https?:\/\//i.test(trimmed);
  if (!isAbsolute && trimmed === '/api') {
    // Base is the proxy root already; avoid double /api when endpoints include it
    return '';
  }
  if (isAbsolute && trimmed.toLowerCase().endsWith('/api')) {
    return trimmed.slice(0, -4);
  }

  return trimmed || '/';
})();

const apiClient = axios.create({
  baseURL: normalizedBaseUrl,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - normalize URL and add auth header
apiClient.interceptors.request.use((config) => {
  // Avoid double /api when baseURL already points to /api proxy
  if (config.url?.startsWith('/api/api/')) {
    config.url = config.url.replace(/^\/api\/api\//, '/api/');
  }

  const apiKey = getEffectiveApiKey();
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
      clearStoredApiKey();
      console.warn('API authentication failed - configure a valid API key in Settings.');
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
