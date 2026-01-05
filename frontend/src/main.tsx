import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import './index.css'
import App from './App.tsx'
import { configLoader } from './config'
import { queryClient } from './lib/queryClient'

// Validate configuration on startup
let config;
try {
  config = configLoader.loadFromEnv();

  if (!configLoader.isValid()) {
    const errors = configLoader.getValidationErrors();
    console.warn('⚠️ Configuration validation warnings:', errors);

    // In development/staging, we log warnings but continue
    // Only halt in production if critical
    if (config?.app?.environment === 'production') {
      const hasCriticalErrors = errors.some(e => e.includes('critical'));
      if (hasCriticalErrors) {
        console.error('Critical configuration errors:', errors);
        // Don't throw - show error in UI instead
      }
    }
  }
} catch (error) {
  console.error('Configuration loading failed:', error);
  // Continue anyway - components will handle missing config gracefully
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
)
