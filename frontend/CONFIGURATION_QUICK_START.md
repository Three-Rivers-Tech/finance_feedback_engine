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
cp .env.local.example .env.local

# Edit with your values (VITE_API_BASE_URL is REQUIRED)
nano .env.local
```

**Minimum `.env.local` (REQUIRED):**

```env
# REQUIRED: Backend API endpoint - must be set
VITE_API_BASE_URL=http://localhost:8000

# REQUIRED: API key for development (minimum 8 characters)
VITE_API_KEY=your-personal-dev-key-here
```

⚠️ **The `VITE_API_BASE_URL` environment variable is MANDATORY.** Application will not run without it.

### 3. Test Configuration

```bash
# Validate current config
npm run validate-config

# Expected output:
# ✓ Configuration validation passed
# Environment: development
# API Base URL: http://localhost:8000

# Run config tests
npm run test:config
```

### 4. Use in Your Code

```typescript
import { config } from '@/config';

// Use validated, type-safe config
const apiUrl = config.api.baseUrl;     // "http://localhost:8000"
const timeout = config.api.timeout;     // 30000
const apiKey = config.api.apiKey;       // "your-personal-dev-key-here"
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

### ⚠️ REQUIRED Environment Variables

```env
# API Configuration - MANDATORY
# Must point to running backend server
VITE_API_BASE_URL=http://localhost:8000

# Services
VITE_GRAFANA_URL=http://localhost:3001

# Polling Intervals (milliseconds, optional)
VITE_POLLING_INTERVAL_CRITICAL=3000
VITE_POLLING_INTERVAL_MEDIUM=5000

# API Key (optional for development, required for staging/prod)
VITE_API_KEY=your-api-key
```

### Environment-Specific Setup

**Development:**
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=dev-key-12345678  # Optional minimum 8 chars
```

**Staging:**
```env
VITE_API_BASE_URL=https://api-staging.example.com
VITE_API_KEY=staging-key-with-16-chars  # Recommended
```

**Production:**
```env
VITE_API_BASE_URL=https://api.example.com
VITE_API_KEY=production-key-with-32-chars  # Required
```

### Environment File Precedence

1. Environment variables (e.g., `VITE_API_BASE_URL=value`)
2. `.env.local` (development only, git-ignored)
3. `.env.{mode}` (e.g., `.env.production`)
4. `.env` (shared defaults)
5. Hardcoded defaults (for optional variables)

## 🐛 Troubleshooting

### ❌ "API base URL is required. Set VITE_API_BASE_URL environment variable"

**Solution:**

1. Create or edit `.env.local`:
   ```bash
   cp .env.local.example .env.local
   nano .env.local
   ```

2. Add the required variable:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   VITE_API_KEY=dev-key-12345678
   ```

3. Restart the dev server:
   ```bash
   npm run dev
   ```

### ❌ "Configuration validation failed"

```bash
# Check what's wrong in detail
npm run validate-config -- --verbose

# Common issues:
# - VITE_API_BASE_URL not set or empty
# - Invalid URL format (must include http:// or https://)
# - Polling interval out of range (1000-60000 ms)
# - Weak API key (avoided patterns: "test", "example", "demo")
```

### ❌ "API requests fail / Cannot reach server"

1. Verify backend is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check if URL is correct in `.env.local`:
   ```bash
   grep VITE_API_BASE_URL .env.local
   ```

3. If backend is on different port:
   ```env
   VITE_API_BASE_URL=http://localhost:YOUR_PORT
   ```

### ❌ "HTTPS required in production/staging"

Use HTTPS URL (not HTTP):
```env
# ❌ Wrong
VITE_API_BASE_URL=http://api-staging.example.com

# ✓ Correct
VITE_API_BASE_URL=https://api-staging.example.com
```

## 📚 Documentation

- **Full Environment Setup Guide:** [ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md) ⭐ **Read this first!**
- **Security Report:** `CONFIGURATION_SECURITY_REPORT.md`
- **Implementation Summary:** `CONFIGURATION_VALIDATION_SUMMARY.md`
- **Config System Code:** `src/config/`

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
