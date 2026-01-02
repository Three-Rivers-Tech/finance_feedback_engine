import { vi } from 'vitest';
import '@testing-library/jest-dom';

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

// Mock import.meta.env - use Object.defineProperty for proper mocking
Object.defineProperty(import.meta, 'env', {
  value: {
    MODE: 'development',
    VITE_API_BASE_URL: 'http://localhost:8000',
    VITE_GRAFANA_URL: 'http://localhost:3001',
    VITE_POLLING_INTERVAL_CRITICAL: '3000',
    VITE_POLLING_INTERVAL_MEDIUM: '5000',
    VITE_API_KEY: 'myvalidkey12345',
  },
  writable: true,
  configurable: true,
});
