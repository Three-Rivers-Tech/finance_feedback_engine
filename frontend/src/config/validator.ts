import { ZodError } from 'zod';
import {
  configSchema,
  environmentSchemas,
  securityRules,
  type AppConfig,
  type Environment,
  type ValidationError,
  type ValidationResult,
} from './schema';

/**
 * Configuration Validator
 * Validates application configuration with environment-specific rules
 */
export class ConfigValidator {
  private environment: Environment;
  private strict: boolean;

  constructor(environment: Environment = 'development', strict = false) {
    this.environment = environment;
    this.strict = strict;
  }

  /**
   * Validate configuration against schema and security rules
   */
  validate(config: unknown): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];

    // Step 1: Schema validation
    const schemaResult = this.validateSchema(config);
    if (!schemaResult.valid) {
      errors.push(...(schemaResult.errors || []));
    }

    // If schema validation fails in strict mode, return immediately
    if (!schemaResult.valid && this.strict) {
      return { valid: false, errors };
    }

    // Step 2: Security validation (even if schema validation fails)
    const securityResult = this.validateSecurity(
      schemaResult.config || (config as AppConfig)
    );
    errors.push(...securityResult.errors);
    warnings.push(...securityResult.warnings);

    // Step 3: Environment-specific validation
    const envResult = this.validateEnvironment(
      schemaResult.config || (config as AppConfig)
    );
    errors.push(...envResult.errors);
    warnings.push(...envResult.warnings);

    const valid = errors.length === 0;
    return {
      valid,
      errors: errors.length > 0 ? errors : undefined,
      warnings: warnings.length > 0 ? warnings : undefined,
      config: schemaResult.config,
    };
  }

  /**
   * Validate against Zod schema
   */
  private validateSchema(config: unknown): {
    valid: boolean;
    errors?: ValidationError[];
    config?: AppConfig;
  } {
    try {
      const schema =
        environmentSchemas[this.environment] || configSchema;
      const validatedConfig = schema.parse(config);
      return { valid: true, config: validatedConfig };
    } catch (error) {
      if (error instanceof ZodError) {
        const errors: ValidationError[] = error.errors.map((err) => ({
          path: err.path.join('.'),
          message: err.message,
          severity: 'critical' as const,
          rule: 'schema_validation',
        }));
        return { valid: false, errors };
      }
      return {
        valid: false,
        errors: [
          {
            path: '/',
            message: 'Unknown validation error',
            severity: 'critical',
            rule: 'unknown',
          },
        ],
      };
    }
  }

  /**
   * Validate security rules
   */
  private validateSecurity(config: AppConfig): {
    errors: ValidationError[];
    warnings: ValidationError[];
  } {
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];
    const rules = securityRules[this.environment];

    // Check HTTPS requirement
    if (rules.requireHttps) {
      if (
        config.api.baseUrl.startsWith('http://') &&
        !this.isLocalhostUrl(config.api.baseUrl)
      ) {
        errors.push({
          path: 'api.baseUrl',
          message: `HTTPS required in ${this.environment} environment`,
          severity: 'critical',
          rule: 'require_https',
        });
      }

      if (
        config.services.grafana.url.startsWith('http://') &&
        !this.isLocalhostUrl(config.services.grafana.url)
      ) {
        errors.push({
          path: 'services.grafana.url',
          message: `HTTPS required for external services in ${this.environment}`,
          severity: 'high',
          rule: 'require_https',
        });
      }
    }

    // Check API key length
    if (config.api.apiKey) {
      if (config.api.apiKey.length < rules.minApiKeyLength) {
        // Push to errors in staging/production, warnings in development
        if (this.environment === 'development') {
          warnings.push({
            path: 'api.apiKey',
            message: `API key should be at least ${rules.minApiKeyLength} characters in ${this.environment}`,
            severity: 'high',
            rule: 'min_api_key_length',
          });
        } else {
          errors.push({
            path: 'api.apiKey',
            message: `API key must be at least ${rules.minApiKeyLength} characters in ${this.environment}`,
            severity: 'high',
            rule: 'min_api_key_length',
          });
        }
      }

      // Check for weak/example API keys - ALWAYS errors (all environments)
      if (this.isWeakApiKey(config.api.apiKey)) {
        errors.push({
          path: 'api.apiKey',
          message:
            'API key appears to be a placeholder or example value',
          severity: 'high',
          rule: 'weak_api_key',
        });
      }
    } else if (this.environment === 'production') {
      warnings.push({
        path: 'api.apiKey',
        message: 'API key is not set in production environment',
        severity: 'medium',
        rule: 'missing_api_key',
      });
    }

    // Check localhost URLs in non-dev environments
    if (!rules.allowLocalhost) {
      if (this.isLocalhostUrl(config.api.baseUrl)) {
        errors.push({
          path: 'api.baseUrl',
          message: `Localhost URLs not allowed in ${this.environment}`,
          severity: 'high',
          rule: 'no_localhost',
        });
      }
    }

    return { errors, warnings };
  }

  /**
   * Validate environment-specific rules
   */
  private validateEnvironment(config: AppConfig): {
    errors: ValidationError[];
    warnings: ValidationError[];
  } {
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];

    // Validate API base URL is set and non-empty
    if (!config.api.baseUrl || config.api.baseUrl.trim().length === 0) {
      errors.push({
        path: 'api.baseUrl',
        message:
          'API base URL is required. Set VITE_API_BASE_URL environment variable. ' +
          'For development, use http://localhost:8000; ' +
          'for staging/production, use HTTPS URL (e.g., https://api.example.com).',
        severity: 'critical',
        rule: 'required_base_url',
      });
    }

    // Validate polling intervals are reasonable
    if (config.polling.critical < 1000) {
      warnings.push({
        path: 'polling.critical',
        message:
          'Critical polling interval less than 1 second may cause performance issues',
        severity: 'medium',
        rule: 'polling_interval_warning',
      });
    }

    if (config.polling.critical > config.polling.medium) {
      warnings.push({
        path: 'polling.critical',
        message:
          'Critical polling interval should be less than medium interval',
        severity: 'low',
        rule: 'polling_interval_ordering',
      });
    }

    // Validate API timeout
    if (config.api.timeout > 60000) {
      warnings.push({
        path: 'api.timeout',
        message: 'API timeout over 60 seconds may cause poor UX',
        severity: 'low',
        rule: 'api_timeout_warning',
      });
    }

    return { errors, warnings };
  }

  /**
   * Check if URL is localhost
   */
  private isLocalhostUrl(url: string): boolean {
    return (
      url.includes('localhost') ||
      url.includes('127.0.0.1') ||
      url.includes('[::1]')
    );
  }

  /**
   * Check for weak/example API keys
   */
  private isWeakApiKey(key: string): boolean {
    const weakPatterns = [
      /your[_-]?api[_-]?key/i,
      /example/i,
      /test/i,
      /demo/i,
      /dev[_-]?key/i,
      /^(123|abc|xxx)/i,
    ];

    return weakPatterns.some((pattern) => pattern.test(key));
  }

  /**
   * Get current environment
   */
  getEnvironment(): Environment {
    return this.environment;
  }

  /**
   * Set environment
   */
  setEnvironment(env: Environment): void {
    this.environment = env;
  }
}

/**
 * Create a validator instance
 */
export function createValidator(
  environment?: Environment,
  strict?: boolean
): ConfigValidator {
  return new ConfigValidator(environment, strict);
}

/**
 * Quick validation helper
 */
export function validateConfig(
  config: unknown,
  environment?: Environment
): ValidationResult {
  const validator = createValidator(environment);
  return validator.validate(config);
}
