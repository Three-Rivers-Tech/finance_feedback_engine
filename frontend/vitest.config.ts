import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/config/__tests__/setup.ts'],
    env: {
      MODE: 'development',
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_GRAFANA_URL: 'http://localhost:3001',
      VITE_POLLING_INTERVAL_CRITICAL: '3000',
      VITE_POLLING_INTERVAL_MEDIUM: '5000',
      VITE_API_KEY: 'myvalidkey12345',
    },
    exclude: [
      'node_modules/**',
      '**/node_modules/**',
      'e2e/**',
      '**/*.e2e.*',
      '**/playwright/**',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/config/__tests__/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/dist/**',
      ],
    },
  },
});
