import { config } from '../config';

// Re-export configuration values for backward compatibility
// Uses validated, type-safe configuration from the config system
export const API_BASE_URL = config.api.baseUrl;
export const GRAFANA_URL = config.services.grafana.url;

// Map to uppercase keys for backward compatibility with existing code
export const POLL_INTERVALS = {
  CRITICAL: config.polling.critical,
  MEDIUM: config.polling.medium,
};

export const APP_VERSION = config.app.version;
