import { describe, it, expect, beforeEach } from 'vitest';
import { ConfigValidator } from '../validator';
import type { AppConfig } from '../schema';

describe('ConfigValidator', () => {
  let validator: ConfigValidator;

  const validDevConfig: AppConfig = {
    api: {
      baseUrl: 'http://localhost:8000',
      timeout: 30000,
      apiKey: 'myvalidkey12345',
    },
    services: {
      grafana: {
        url: 'http://localhost:3001',
      },
    },
    polling: {
      critical: 3000,
      medium: 5000,
    },
    app: {
      version: '1.0.0',
      environment: 'development',
    },
  };

  describe('Development Environment', () => {
    beforeEach(() => {
      validator = new ConfigValidator('development', false);
    });

    it('should validate valid development config', () => {
      const result = validator.validate(validDevConfig);
      expect(result.valid).toBe(true);
      expect(result.errors).toBeUndefined();
    });

    it('should allow HTTP URLs in development', () => {
      const result = validator.validate(validDevConfig);
      expect(result.valid).toBe(true);
    });

    it('should allow localhost URLs in development', () => {
      const config = {
        ...validDevConfig,
        api: {
          ...validDevConfig.api,
          baseUrl: 'http://localhost:8000',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(true);
    });

    it('should accept short API keys in development', () => {
      const config = {
        ...validDevConfig,
        api: {
          ...validDevConfig.api,
          apiKey: 'short123',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(true);
    });

    it('should detect weak API keys', () => {
      const weakKeys = [
        'your_api_key_here',
        'example-key',
        'test-key',
        'dev-key',
      ];

      weakKeys.forEach((key) => {
        const config = {
          ...validDevConfig,
          api: {
            ...validDevConfig.api,
            apiKey: key,
          },
        };
        const result = validator.validate(config);
        expect(result.valid).toBe(false);
        expect(result.errors).toBeDefined();
        expect(result.errors?.some((e) => e.rule === 'weak_api_key')).toBe(
          true
        );
      });
    });
  });

  describe('Production Environment', () => {
    beforeEach(() => {
      validator = new ConfigValidator('production', false);
    });

    const validProdConfig: AppConfig = {
      api: {
        baseUrl: 'https://api.example.com',
        timeout: 30000,
        apiKey: 'prod-key-very-long-and-secure-12345678901234567890',
      },
      services: {
        grafana: {
          url: 'https://grafana.example.com',
        },
      },
      polling: {
        critical: 3000,
        medium: 5000,
      },
      app: {
        version: '1.0.0',
        environment: 'production',
      },
    };

    it('should validate valid production config', () => {
      const result = validator.validate(validProdConfig);
      expect(result.valid).toBe(true);
    });

    it('should require HTTPS in production', () => {
      const config = {
        ...validProdConfig,
        api: {
          ...validProdConfig.api,
          baseUrl: 'http://api.example.com',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
      expect(result.errors?.some((e) => e.rule === 'require_https')).toBe(
        true
      );
    });

    it('should not allow localhost in production', () => {
      const config = {
        ...validProdConfig,
        api: {
          ...validProdConfig.api,
          baseUrl: 'http://localhost:8000',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
      expect(
        result.errors?.some((e) => e.rule === 'no_localhost' || e.rule === 'require_https')
      ).toBe(true);
    });

    it('should require long API keys in production', () => {
      const config = {
        ...validProdConfig,
        api: {
          ...validProdConfig.api,
          apiKey: 'short',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
      expect(
        result.errors?.some((e) => e.rule === 'min_api_key_length')
      ).toBe(true);
    });

    it('should warn if API key is missing in production', () => {
      const config = {
        ...validProdConfig,
        api: {
          ...validProdConfig.api,
          apiKey: undefined,
        },
      };
      const result = validator.validate(config);
      expect(result.warnings?.some((w) => w.rule === 'missing_api_key')).toBe(
        true
      );
    });

    it('should allow relative URLs in production', () => {
      const config = {
        ...validProdConfig,
        api: {
          ...validProdConfig.api,
          baseUrl: '/api',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(true);
    });
  });

  describe('Schema Validation', () => {
    beforeEach(() => {
      validator = new ConfigValidator('development', false);
    });

    it('should reject invalid polling intervals', () => {
      const config = {
        ...validDevConfig,
        polling: {
          critical: 500, // Too low
          medium: 5000,
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
    });

    it('should reject polling intervals over 60 seconds', () => {
      const config = {
        ...validDevConfig,
        polling: {
          critical: 70000,
          medium: 5000,
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
    });

    it('should reject invalid URL formats', () => {
      const config = {
        ...validDevConfig,
        api: {
          ...validDevConfig.api,
          baseUrl: 'not-a-url',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
    });

    it('should reject empty baseUrl', () => {
      const config = {
        ...validDevConfig,
        api: {
          ...validDevConfig.api,
          baseUrl: '',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
      expect(result.errors).toBeDefined();
      expect(
        result.errors?.some(
          (e) =>
            e.path === 'api.baseUrl' &&
            e.rule === 'required_base_url'
        )
      ).toBe(true);
    });

    it('should reject whitespace-only baseUrl', () => {
      const config = {
        ...validDevConfig,
        api: {
          ...validDevConfig.api,
          baseUrl: '   ',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
      expect(result.errors).toBeDefined();
    });

    it('should reject invalid version format', () => {
      const config = {
        ...validDevConfig,
        app: {
          ...validDevConfig.app,
          version: 'invalid',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
    });

    it('should warn when critical interval > medium interval', () => {
      const config = {
        ...validDevConfig,
        polling: {
          critical: 10000,
          medium: 5000,
        },
      };
      const result = validator.validate(config);
      expect(
        result.warnings?.some(
          (w) => w.rule === 'polling_interval_ordering'
        )
      ).toBe(true);
    });
  });

  describe('Staging Environment', () => {
    beforeEach(() => {
      validator = new ConfigValidator('staging', false);
    });

    const validStagingConfig: AppConfig = {
      api: {
        baseUrl: 'https://staging-api.example.com',
        timeout: 30000,
        apiKey: 'staging-key-16chars',
      },
      services: {
        grafana: {
          url: 'https://staging-grafana.example.com',
        },
      },
      polling: {
        critical: 3000,
        medium: 5000,
      },
      app: {
        version: '1.0.0',
        environment: 'staging',
      },
    };

    it('should validate valid staging config', () => {
      const result = validator.validate(validStagingConfig);
      expect(result.valid).toBe(true);
    });

    it('should require HTTPS in staging', () => {
      const config = {
        ...validStagingConfig,
        api: {
          ...validStagingConfig.api,
          baseUrl: 'http://staging-api.example.com',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
    });

    it('should require 16+ character API keys in staging', () => {
      const config = {
        ...validStagingConfig,
        api: {
          ...validStagingConfig.api,
          apiKey: 'short-key',
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
    });
  });

  describe('Strict Mode', () => {
    it('should fail fast in strict mode on schema errors', () => {
      validator = new ConfigValidator('production', true);
      const config = {
        ...validDevConfig,
        polling: {
          critical: 'invalid', // Wrong type
          medium: 5000,
        },
      };
      const result = validator.validate(config);
      expect(result.valid).toBe(false);
      expect(result.errors).toBeDefined();
    });
  });
});
