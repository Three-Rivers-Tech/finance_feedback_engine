import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { configLoader } from './config'

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
    <App />
  </StrictMode>,
)
