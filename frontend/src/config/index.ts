/**
 * Configuration Module
 * Centralized configuration management with validation
 */

export { config, getConfig, reloadConfig } from './loader';
export { ConfigValidator, validateConfig, createValidator } from './validator';
export {
  configSchema,
  environmentSchemas,
  securityRules,
  type AppConfig,
  type Environment,
  type ValidationError,
  type ValidationResult,
} from './schema';
export { ConfigLoader, configLoader } from './loader';
