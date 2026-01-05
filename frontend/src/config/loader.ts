import { ConfigValidator } from './validator';
import { type AppConfig, type Environment } from './schema';

// App version - defined here to avoid circular dependency with constants.ts
const APP_VERSION = '1.0.0';

/**
 * Configuration Loader
 * Loads and validates configuration from environment variables
 */
export class ConfigLoader {
  private static instance: ConfigLoader | null = null;
  private config: AppConfig | null = null;
  private validator: ConfigValidator;
  private environment: Environment;

  private constructor() {
    this.environment = this.detectEnvironment();
    this.validator = new ConfigValidator(this.environment, false);
  }

  /**
   * Get singleton instance
   */
  static getInstance(): ConfigLoader {
    if (!ConfigLoader.instance) {
      ConfigLoader.instance = new ConfigLoader();
    }
    return ConfigLoader.instance;
  }

  /**
   * Detect current environment
   */
  private detectEnvironment(): Environment {
    const mode = import.meta.env.MODE;
    const nodeEnv = import.meta.env.VITE_NODE_ENV;

    if (mode === 'production' || nodeEnv === 'production') {
      return 'production';
    }
    if (mode === 'staging' || nodeEnv === 'staging') {
      return 'staging';
    }
    return 'development';
  }

  /**
   * Load configuration from environment variables
   */
  loadFromEnv(): AppConfig {
    // Determine appropriate default baseUrl based on environment
    const getDefaultBaseUrl = (): string => {
      if (this.environment === 'development') {
        return 'http://localhost:8000'; // Safe default for local development
      }
      // Staging and production must explicitly set this
      return '';
    };

    const rawConfig = {
      api: {
        baseUrl:
          import.meta.env.VITE_API_BASE_URL || getDefaultBaseUrl(),
        timeout: 30000,
        apiKey: this.loadApiKey(),
      },
      services: {
        grafana: {
          url:
            import.meta.env.VITE_GRAFANA_URL ||
            'http://localhost:3001',
        },
      },
      polling: {
        critical: this.parseNumber(
          import.meta.env.VITE_POLLING_INTERVAL_CRITICAL,
          3000
        ),
        medium: this.parseNumber(
          import.meta.env.VITE_POLLING_INTERVAL_MEDIUM,
          5000
        ),
      },
      app: {
        version: APP_VERSION,
        environment: this.environment,
      },
    };

    // Validate configuration
    const result = this.validator.validate(rawConfig);

    // Log validation results
    if (!result.valid) {
      // Special handling for empty baseUrl
      const hasEmptyBaseUrl = result.errors?.some(
        (e) => e.path === 'api.baseUrl' && e.message?.includes('empty')
      );

      // In development, only log errors without blocking - use fallback config
      if (this.environment === 'development') {
        console.debug(`Configuration: ${result.errors?.length || 0} validation error(s) in dev mode (not blocking)`);
      } else {
        console.error('Configuration validation failed:', result.errors);
      }

      // Provide helpful guidance for missing baseUrl
      if (hasEmptyBaseUrl && this.environment !== 'development') {
        console.error(
          `\n⚠️  API Base URL not configured!\n` +
          `Set the VITE_API_BASE_URL environment variable:\n` +
          `  • For development: http://localhost:8000\n` +
          `  • For staging: https://api-staging.example.com\n` +
          `  • For production: https://api.example.com\n` +
          `See frontend/ENVIRONMENT_SETUP.md for detailed instructions.`
        );
      }

      // In production, throw error for critical issues
      if (this.environment === 'production') {
        const criticalErrors = result.errors?.filter(
          (e) => e.severity === 'critical'
        );
        if (criticalErrors && criticalErrors.length > 0) {
          throw new Error(
            `Critical configuration errors:\n${criticalErrors
              .map((e) => `  - ${e.path}: ${e.message}`)
              .join('\n')}`
          );
        }
      }
    }

    // Log warnings (suppress in development to reduce console noise)
    if (result.warnings && result.warnings.length > 0) {
      if (this.environment !== 'development') {
        console.warn('Configuration warnings:', result.warnings);
      } else {
        // In dev mode, just log count of warnings to reduce noise
        console.debug(`Configuration: ${result.warnings.length} dev-mode warning(s) suppressed`);
      }
    }

    this.config = result.config || (rawConfig as AppConfig);
    return this.config;
  }

  /**
   * Load API key from localStorage or environment
   */
  private loadApiKey(): string | undefined {
    // Try localStorage first (user-provided key takes precedence)
    const storedKey = localStorage.getItem('api_key');
    if (storedKey) {
      return storedKey;
    }

    // Fall back to environment variable
    const envKey = import.meta.env.VITE_API_KEY;
    if (envKey) {
      return envKey;
    }

    return undefined;
  }

  /**
   * Parse number from environment variable with fallback
   */
  private parseNumber(value: string | undefined, fallback: number): number {
    if (!value) return fallback;
    const parsed = Number(value);
    return isNaN(parsed) ? fallback : parsed;
  }

  /**
   * Get loaded configuration
   */
  getConfig(): AppConfig {
    if (!this.config) {
      return this.loadFromEnv();
    }
    return this.config;
  }

  /**
   * Reload configuration
   */
  reload(): AppConfig {
    this.config = null;
    return this.loadFromEnv();
  }

  /**
   * Get current environment
   */
  getEnvironment(): Environment {
    return this.environment;
  }

  /**
   * Check if configuration is valid
   */
  isValid(): boolean {
    if (!this.config) {
      this.loadFromEnv();
    }
    const result = this.validator.validate(this.config!);
    return result.valid;
  }

  /**
   * Get validation errors
   */
  getValidationErrors(): string[] {
    if (!this.config) {
      this.loadFromEnv();
    }
    const result = this.validator.validate(this.config!);
    return result.errors?.map((e) => `${e.path}: ${e.message}`) || [];
  }
}

/**
 * Global configuration instance
 */
export const configLoader = ConfigLoader.getInstance();

/**
 * Get current configuration
 */
export function getConfig(): AppConfig {
  return configLoader.getConfig();
}

/**
 * Reload configuration
 */
export function reloadConfig(): AppConfig {
  return configLoader.reload();
}

/**
 * Export configuration for use in app
 */
export const config = configLoader.getConfig();
