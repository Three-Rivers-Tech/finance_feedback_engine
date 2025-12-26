import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { configLoader } from './config'

// Validate configuration on startup
const config = configLoader.loadFromEnv();

if (!configLoader.isValid()) {
  const errors = configLoader.getValidationErrors();
  console.warn('⚠️ Configuration validation warnings:', errors);

  // In production, critical errors would halt startup
  // In development, we log warnings and continue
  if (config.app.environment === 'production') {
    const hasCriticalErrors = errors.some(e => e.includes('critical'));
    if (hasCriticalErrors) {
      throw new Error('Critical configuration errors detected. Cannot start application.');
    }
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
