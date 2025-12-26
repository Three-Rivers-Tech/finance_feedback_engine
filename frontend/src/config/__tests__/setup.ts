import { vi } from 'vitest';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock import.meta.env
vi.mock('import.meta', () => ({
  env: {
    MODE: 'development',
    VITE_API_BASE_URL: 'http://localhost:8000',
    VITE_GRAFANA_URL: 'http://localhost:3001',
    VITE_POLLING_INTERVAL_CRITICAL: '3000',
    VITE_POLLING_INTERVAL_MEDIUM: '5000',
    VITE_API_KEY: 'myvalidkey12345',
  },
}));
