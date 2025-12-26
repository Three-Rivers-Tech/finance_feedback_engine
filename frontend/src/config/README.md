# Configuration System Documentation

## Overview

The Finance Feedback Engine frontend uses a robust configuration management system with runtime validation, environment-specific rules, and comprehensive security checks.

## Architecture

```
src/config/
├── schema.ts         # Zod schemas and type definitions
├── validator.ts      # Configuration validation logic
├── loader.ts         # Configuration loader and singleton
├── index.ts          # Public API exports
└── __tests__/        # Test suite
    ├── validator.test.ts
    ├── loader.test.ts
    └── setup.ts
```

## Configuration Options

### API Configuration

Configuration for backend API communication.

**`api.baseUrl`** (string, required)
- **Type:** URL (http://, https://, or relative path)
- **Description:** Base URL for backend API
- **Example:**
  - Development: `http://localhost:8000`
  - Production: `https://api.example.com` or `/api`
- **Validation:**
  - Must be valid URL format
  - HTTPS required in production (except localhost)
  - Relative URLs allowed in production

**`api.timeout`** (number, optional)
- **Type:** Positive integer (milliseconds)
- **Description:** API request timeout
- **Default:** `30000` (30 seconds)
- **Validation:**
  - Must be positive integer
  - Warning if > 60000ms

**`api.apiKey`** (string, optional)
- **Type:** String
- **Description:** API authentication key
- **Example:** Set in `.env.local` or localStorage
- **Validation:**
  - Development: Min 8 characters
  - Staging: Min 16 characters
  - Production: Min 32 characters
  - Weak keys rejected (e.g., "your_api_key_here", "test", "example")

### Services Configuration

External service endpoints.

**`services.grafana.url`** (string, required)
- **Type:** URL
- **Description:** Grafana dashboard URL
- **Example:** `http://localhost:3001` or `https://grafana.example.com`
- **Validation:** Same as API URLs

### Polling Configuration

Data polling intervals in milliseconds.

**`polling.critical`** (number, required)
- **Type:** Integer (1000-60000)
- **Description:** Polling interval for critical data updates
- **Default:** `3000` (3 seconds)
- **Validation:**
  - Min: 1000ms (1 second)
  - Max: 60000ms (60 seconds)
  - Warning if < 1000ms

**`polling.medium`** (number, required)
- **Type:** Integer (1000-60000)
- **Description:** Polling interval for medium priority data
- **Default:** `5000` (5 seconds)
- **Validation:** Same as `polling.critical`

### App Metadata

Application information.

**`app.version`** (string, required)
- **Type:** Semantic version string
- **Description:** Application version
- **Example:** `1.0.0`
- **Validation:** Must match semver format (x.y.z)

**`app.environment`** (enum, required)
- **Type:** `'development' | 'staging' | 'production'`
- **Description:** Current environment
- **Validation:** Must be one of the allowed values

## Environment Files

### `.env.example`
Template file with example values. Never contains real secrets.

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GRAFANA_URL=http://localhost:3001
VITE_POLLING_INTERVAL_CRITICAL=3000
VITE_POLLING_INTERVAL_MEDIUM=5000
VITE_API_KEY=your_api_key_here
```

### `.env`
Development environment configuration. **DO NOT commit with real secrets.**

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GRAFANA_URL=http://localhost:3001
VITE_POLLING_INTERVAL_CRITICAL=3000
VITE_POLLING_INTERVAL_MEDIUM=5000
# VITE_API_KEY not set - will use localStorage
```

### `.env.production`
Production environment configuration.

```env
VITE_API_BASE_URL=/api
VITE_GRAFANA_URL=https://grafana.example.com
VITE_POLLING_INTERVAL_CRITICAL=3000
VITE_POLLING_INTERVAL_MEDIUM=5000
# VITE_API_KEY should be set via environment or secrets manager
```

### `.env.local`
Local overrides (gitignored). Use for developer-specific settings.

```env
VITE_API_KEY=your-personal-api-key-here
```

## Usage

### Basic Usage

```typescript
import { config } from '@/config';

// Use configuration
const response = await fetch(`${config.api.baseUrl}/endpoint`);
```

### Loading Configuration

```typescript
import { getConfig, reloadConfig } from '@/config';

// Get current config
const config = getConfig();

// Reload configuration (e.g., after env change)
const newConfig = reloadConfig();
```

### Validation

```typescript
import { validateConfig, ConfigValidator } from '@/config';

// Quick validation
const result = validateConfig(configData, 'production');

if (!result.valid) {
  console.error('Validation errors:', result.errors);
}

// Advanced validation
const validator = new ConfigValidator('production', true);
const result = validator.validate(configData);
```

### Type-Safe Access

```typescript
import type { AppConfig } from '@/config';

function useApiConfig(config: AppConfig) {
  // TypeScript ensures config has correct shape
  const { baseUrl, timeout, apiKey } = config.api;
  // ...
}
```

## Environment-Specific Rules

### Development
- ✅ HTTP URLs allowed
- ✅ Localhost URLs allowed
- ✅ Debug mode allowed
- ⚠️ Min API key length: 8 characters
- ❌ Weak API keys rejected

### Staging
- ❌ HTTPS required (no localhost exception)
- ❌ No localhost URLs
- ❌ No debug mode
- ⚠️ Min API key length: 16 characters
- ❌ Weak API keys rejected

### Production
- ❌ HTTPS required (relative URLs allowed)
- ❌ No localhost URLs
- ❌ No debug mode
- ⚠️ Min API key length: 32 characters
- ❌ Weak API keys rejected
- ⚠️ Encryption required

## Security Best Practices

### API Key Management

1. **Never commit API keys to git**
   - Use `.env.local` for local development
   - Use `.env.example` as template only

2. **Use environment variables or secrets manager in production**
   ```bash
   export VITE_API_KEY="your-production-key"
   ```

3. **Prefer localStorage for user-provided keys**
   ```typescript
   localStorage.setItem('api_key', userProvidedKey);
   ```

### URL Security

1. **Always use HTTPS in production**
   - Except for relative URLs (proxied by Nginx)

2. **Validate all URLs**
   - System rejects invalid URL formats
   - Localhost blocked in production/staging

### Configuration Validation

1. **Run validation on startup**
   - Critical errors throw in production
   - Warnings logged in development

2. **Use strict mode for CI/CD**
   ```typescript
   const validator = new ConfigValidator('production', true);
   ```

## Error Handling

### Validation Errors

```typescript
{
  path: 'api.baseUrl',
  message: 'HTTPS required in production environment',
  severity: 'critical',
  rule: 'require_https'
}
```

Severity levels:
- **critical**: Blocks in production, must fix
- **high**: Should fix, may block in strict mode
- **medium**: Should fix, logged as warning
- **low**: Optional improvement

### Handling Validation Failures

```typescript
import { ConfigLoader } from '@/config';

const loader = ConfigLoader.getInstance();

try {
  const config = loader.loadFromEnv();

  if (!loader.isValid()) {
    const errors = loader.getValidationErrors();
    console.error('Config validation warnings:', errors);
  }
} catch (error) {
  // Critical validation error in production
  console.error('Failed to load configuration:', error);
}
```

## Testing

### Run Configuration Tests

```bash
# Run all config tests
npm run test:config

# Run with coverage
npm run test:coverage

# Run in watch mode
npm test
```

### Test Structure

```typescript
import { describe, it, expect } from 'vitest';
import { ConfigValidator } from '@/config';

describe('Custom Config Validation', () => {
  it('should validate custom config', () => {
    const validator = new ConfigValidator('production');
    const result = validator.validate(myConfig);
    expect(result.valid).toBe(true);
  });
});
```

## Migration Guide

### From Old System

If migrating from the old constants-based system:

**Before:**
```typescript
// src/utils/constants.ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
```

**After:**
```typescript
// Use validated config instead
import { config } from '@/config';
const apiUrl = config.api.baseUrl;
```

### Updating Constants File

Update `src/utils/constants.ts` to use the new config system:

```typescript
import { config } from '@/config';

export const API_BASE_URL = config.api.baseUrl;
export const GRAFANA_URL = config.services.grafana.url;
export const POLL_INTERVALS = config.polling;
export const APP_VERSION = config.app.version;
```

## Troubleshooting

### Issue: "Configuration validation failed"

**Cause:** Config doesn't meet validation rules

**Solution:**
1. Check validation errors: `loader.getValidationErrors()`
2. Review environment-specific rules
3. Fix configuration values
4. Reload: `reloadConfig()`

### Issue: "API key required"

**Cause:** No API key in env or localStorage

**Solution:**
1. Set in `.env.local`: `VITE_API_KEY=your-key`
2. Or store in localStorage: `localStorage.setItem('api_key', 'key')`

### Issue: "HTTPS required in production"

**Cause:** Using HTTP URL in production

**Solution:**
1. Use HTTPS URL: `https://api.example.com`
2. Or use relative URL: `/api` (proxied by Nginx)

## API Reference

### ConfigValidator

```typescript
class ConfigValidator {
  constructor(environment: Environment, strict: boolean)
  validate(config: unknown): ValidationResult
  getEnvironment(): Environment
  setEnvironment(env: Environment): void
}
```

### ConfigLoader

```typescript
class ConfigLoader {
  static getInstance(): ConfigLoader
  loadFromEnv(): AppConfig
  getConfig(): AppConfig
  reload(): AppConfig
  getEnvironment(): Environment
  isValid(): boolean
  getValidationErrors(): string[]
}
```

### Helper Functions

```typescript
// Quick config access
getConfig(): AppConfig
reloadConfig(): AppConfig

// Validation helpers
validateConfig(config: unknown, env?: Environment): ValidationResult
createValidator(env?: Environment, strict?: boolean): ConfigValidator
```

## Contributing

### Adding New Config Options

1. **Update schema** (`schema.ts`):
   ```typescript
   export const configSchema = z.object({
     // ... existing fields
     newFeature: z.object({
       enabled: z.boolean(),
       timeout: z.number().positive(),
     }),
   });
   ```

2. **Update loader** (`loader.ts`):
   ```typescript
   loadFromEnv(): AppConfig {
     return {
       // ... existing fields
       newFeature: {
         enabled: import.meta.env.VITE_NEW_FEATURE_ENABLED === 'true',
         timeout: this.parseNumber(import.meta.env.VITE_NEW_FEATURE_TIMEOUT, 5000),
       },
     };
   }
   ```

3. **Add tests** (`__tests__/validator.test.ts`):
   ```typescript
   it('should validate new feature config', () => {
     const config = { ...validConfig, newFeature: { enabled: true, timeout: 5000 } };
     expect(validator.validate(config).valid).toBe(true);
   });
   ```

4. **Update documentation** (this file)

## License

Part of the Finance Feedback Engine project.
