import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ConfigLoader } from '../loader';

describe('ConfigLoader', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('Environment Detection', () => {
    it('should detect development environment by default', () => {
      const loader = ConfigLoader.getInstance();
      expect(loader.getEnvironment()).toBe('development');
    });
  });

  describe('Configuration Loading', () => {
    it('should load configuration from environment variables', () => {
      const loader = ConfigLoader.getInstance();
      const config = loader.getConfig();

      expect(config).toBeDefined();
      expect(config.api).toBeDefined();
      expect(config.services).toBeDefined();
      expect(config.polling).toBeDefined();
      expect(config.app).toBeDefined();
    });

    it('should use default values when env vars are missing', () => {
      const loader = ConfigLoader.getInstance();
      const config = loader.loadFromEnv();

      expect(config.api.timeout).toBe(30000);
      expect(config.polling.critical).toBeDefined();
      expect(config.polling.medium).toBeDefined();
    });

    it('should prioritize localStorage API key over env var', () => {
      const storedKey = 'stored-api-key-123';
      localStorage.setItem('api_key', storedKey);

      const loader = ConfigLoader.getInstance();
      const config = loader.reload();

      expect(config.api.apiKey).toBe(storedKey);
    });

    it('should fall back to env var when localStorage is empty', () => {
      localStorage.removeItem('api_key');

      const loader = ConfigLoader.getInstance();
      const config = loader.reload();

      // Will use env var or be undefined
      expect(config.api.apiKey).toBeDefined();
    });
  });

  describe('Configuration Reload', () => {
    it('should reload configuration when called', () => {
      const loader = ConfigLoader.getInstance();
      loader.getConfig();

      // Change localStorage
      localStorage.setItem('api_key', 'new-key-12345');

      const config2 = loader.reload();

      expect(config2.api.apiKey).toBe('new-key-12345');
    });
  });

  describe('Validation', () => {
    it('should validate configuration on load', () => {
      const loader = ConfigLoader.getInstance();
      const config = loader.loadFromEnv();

      // Config should be loaded even with warnings
      expect(config).toBeDefined();
    });

    it('should provide validation status', () => {
      const loader = ConfigLoader.getInstance();
      loader.loadFromEnv();

      const isValid = loader.isValid();
      expect(typeof isValid).toBe('boolean');
    });

    it('should provide validation errors', () => {
      const loader = ConfigLoader.getInstance();
      loader.loadFromEnv();

      const errors = loader.getValidationErrors();
      expect(Array.isArray(errors)).toBe(true);
    });
  });

  describe('Singleton Pattern', () => {
    it('should return the same instance', () => {
      const loader1 = ConfigLoader.getInstance();
      const loader2 = ConfigLoader.getInstance();

      expect(loader1).toBe(loader2);
    });
  });
});
