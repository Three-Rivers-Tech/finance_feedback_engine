export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const GRAFANA_URL = import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3001';

export const POLL_INTERVALS = {
  CRITICAL: Number(import.meta.env.VITE_POLLING_INTERVAL_CRITICAL) || 3000,
  MEDIUM: Number(import.meta.env.VITE_POLLING_INTERVAL_MEDIUM) || 5000,
};

export const APP_VERSION = '1.0.0';
