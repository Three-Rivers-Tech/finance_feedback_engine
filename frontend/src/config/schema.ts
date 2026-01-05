import { z } from 'zod';

/**
 * Configuration Schema Definitions
 * Provides runtime validation for all environment variables and configuration
 */

// URL validation schemas
const httpUrlSchema = z.string().url().startsWith('http://');
const httpsUrlSchema = z.string().url().startsWith('https://');
const relativeUrlSchema = z.string().regex(/^\/.*$/);  // Paths starting with / (including just "/")

// Create conditional URL schema based on environment
// This accepts HTTP, HTTPS, and relative URLs (like /api for proxying)
const apiUrlSchema = z.union([
  httpUrlSchema,
  httpsUrlSchema,
  relativeUrlSchema,
]);

// Polling interval validation (in milliseconds)
const pollingIntervalSchema = z
  .number()
  .int()
  .min(1000, 'Polling interval must be at least 1000ms')
  .max(60000, 'Polling interval must not exceed 60000ms');

// API key validation (optional for all environments)
const apiKeySchema = z
  .string()
  .min(1, 'API key must not be empty if provided')
  .optional()
  .or(z.literal(''))
  .transform(val => val === '' ? undefined : val);

/**
 * Main application configuration schema
 */
export const configSchema = z.object({
  // API Configuration
  api: z.object({
    baseUrl: apiUrlSchema.describe('Base URL for backend API'),
    timeout: z
      .number()
      .int()
      .positive()
      .default(30000)
      .describe('API request timeout in milliseconds'),
    apiKey: apiKeySchema.describe('Optional API key for authentication'),
  }),

  // External Services
  services: z.object({
    grafana: z.object({
      url: apiUrlSchema.describe('Grafana dashboard URL'),
    }),
  }),

  // Polling Configuration
  polling: z.object({
    critical: pollingIntervalSchema.describe(
      'Polling interval for critical data'
    ),
    medium: pollingIntervalSchema.describe(
      'Polling interval for medium priority data'
    ),
  }),

  // Application Metadata
  app: z.object({
    version: z.string().regex(/^\d+\.\d+\.\d+$/, 'Must be semver format'),
    environment: z.enum(['development', 'staging', 'production']),
  }),
});

/**
 * Environment-specific validation schemas
 */
export const environmentSchemas = {
  development: configSchema.extend({
    api: z.object({
      baseUrl: z.union([httpUrlSchema, relativeUrlSchema]),
      timeout: z.number().int().positive().default(30000),
      apiKey: apiKeySchema,
    }),
  }),

  staging: configSchema.extend({
    api: z.object({
      baseUrl: httpsUrlSchema,
      timeout: z.number().int().positive().default(30000),
      apiKey: apiKeySchema,
    }),
  }),

  production: configSchema.extend({
    api: z.object({
      baseUrl: z.union([httpsUrlSchema, relativeUrlSchema]),
      timeout: z.number().int().positive().default(30000),
      apiKey: apiKeySchema,
    }),
  }),
};

/**
 * Type inference from schema
 */
export type AppConfig = z.infer<typeof configSchema>;
export type Environment = 'development' | 'staging' | 'production';

/**
 * Security validation rules
 */
export const securityRules = {
  development: {
    requireHttps: false,
    allowDebugMode: true,
    minApiKeyLength: 8,
    allowLocalhost: true,
  },
  staging: {
    requireHttps: true,
    allowDebugMode: false,
    minApiKeyLength: 16,
    allowLocalhost: false,
  },
  production: {
    requireHttps: true,
    allowDebugMode: false,
    minApiKeyLength: 32,
    allowLocalhost: false,
    requireEncryption: true,
  },
} as const;

/**
 * Validation error types
 */
export interface ValidationError {
  path: string;
  message: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  rule: string;
}

/**
 * Validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors?: ValidationError[];
  warnings?: ValidationError[];
  config?: AppConfig;
}
