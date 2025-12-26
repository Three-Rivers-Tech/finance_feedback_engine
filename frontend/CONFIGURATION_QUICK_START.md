# Configuration System - Quick Start Guide

## 🚀 5-Minute Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Create Local Environment File

```bash
# Copy example file
cp .env.example .env.local

# Edit with your values
nano .env.local
```

```env
# .env.local
VITE_API_KEY=your-personal-dev-key-here
```

### 3. Test Configuration

```bash
# Validate current config
npm run validate-config

# Run config tests
npm run test:config
```

### 4. Use in Your Code

```typescript
import { config } from '@/config';

// Use validated, type-safe config
const apiUrl = config.api.baseUrl;
const timeout = config.api.timeout;
```

## 📝 Common Tasks

### Update API Key

```bash
# Option 1: Environment file
echo "VITE_API_KEY=new-key-here" > .env.local

# Option 2: Browser localStorage
localStorage.setItem('api_key', 'new-key-here');
```

### Validate Production Config

```bash
npm run validate-config:prod
```

### Run Tests

```bash
# All config tests
npm run test:config

# Watch mode
npm test

# With coverage
npm run test:coverage
```

### Check for Security Issues

```bash
npm run validate-config -- --verbose
```

## ⚠️ Important Security Notes

1. **Never commit `.env` or `.env.local`** - They contain secrets
2. **Use HTTPS in production** - HTTP is blocked (except localhost)
3. **Rotate API keys** if exposed - Generate new keys immediately
4. **Check .gitignore** - Ensure `.env*` files are ignored

## 🔧 Configuration Options

### Required Environment Variables

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000

# Services
VITE_GRAFANA_URL=http://localhost:3001

# Polling Intervals (milliseconds)
VITE_POLLING_INTERVAL_CRITICAL=3000
VITE_POLLING_INTERVAL_MEDIUM=5000

# Optional: API Key
VITE_API_KEY=your-api-key
```

### Environment-Specific Files

- `.env.example` - Template (commit this)
- `.env` - Development defaults (commit this, no secrets)
- `.env.local` - Local overrides (DO NOT COMMIT)
- `.env.production` - Production config (commit this)

## 🐛 Troubleshooting

### "Configuration validation failed"

```bash
# Check what's wrong
npm run validate-config -- --verbose

# Common issues:
# - Invalid URL format
# - Polling interval out of range (1000-60000)
# - Weak API key (e.g., "test", "example")
```

### "API key required"

```bash
# Set in .env.local
echo "VITE_API_KEY=dev-key-12345678" >> .env.local

# Or use localStorage in browser
localStorage.setItem('api_key', 'your-key');
```

### "HTTPS required in production"

```env
# Use HTTPS
VITE_API_BASE_URL=https://api.example.com

# Or use relative URL (proxied by Nginx)
VITE_API_BASE_URL=/api
```

## 📚 Documentation

- **Full Guide:** `src/config/README.md`
- **Security Report:** `CONFIGURATION_SECURITY_REPORT.md`
- **Implementation Summary:** `CONFIGURATION_VALIDATION_SUMMARY.md`
- **API Reference:** `src/config/README.md#api-reference`

## 💡 Pro Tips

1. **Use validation in CI/CD:**
   ```yaml
   - run: npm run validate-config:prod
   ```

2. **Type-safe access:**
   ```typescript
   import type { AppConfig } from '@/config';

   function myFunction(config: AppConfig) {
     // TypeScript ensures correct usage
   }
   ```

3. **Environment detection:**
   ```typescript
   import { configLoader } from '@/config';

   const env = configLoader.getEnvironment();
   // 'development' | 'staging' | 'production'
   ```

4. **Check validation status:**
   ```typescript
   import { configLoader } from '@/config';

   if (!configLoader.isValid()) {
     console.warn(configLoader.getValidationErrors());
   }
   ```

## 🎯 Next Steps

1. ✅ Install dependencies
2. ✅ Create `.env.local`
3. ✅ Run validation
4. ✅ Run tests
5. ✅ Update your code to use new config
6. ✅ Add validation to CI/CD

## 🆘 Need Help?

- Review the full documentation: `src/config/README.md`
- Check the test files for examples: `src/config/__tests__/`
- Review security best practices: `CONFIGURATION_SECURITY_REPORT.md`

---

**Ready to go?** Start with `npm run validate-config` ✨
