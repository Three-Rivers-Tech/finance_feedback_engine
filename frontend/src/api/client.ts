import axios, { AxiosError } from 'axios';
import { API_BASE_URL } from '../utils/constants';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth header
apiClient.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('api_key');
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
      localStorage.removeItem('api_key');
      window.location.reload();
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
