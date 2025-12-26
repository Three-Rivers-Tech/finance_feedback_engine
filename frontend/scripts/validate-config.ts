#!/usr/bin/env node

/**
 * Configuration Validation CLI
 * Validates configuration files for CI/CD pipelines
 */

import * as fs from 'fs';
import * as path from 'path';
import { ConfigValidator } from '../src/config/validator';
import type { Environment } from '../src/config/schema';

interface ValidationOptions {
  environment: Environment;
  strict: boolean;
  verbose: boolean;
  exitOnError: boolean;
}

class ConfigValidationCLI {
  private options: ValidationOptions;

  constructor(options: Partial<ValidationOptions> = {}) {
    this.options = {
      environment: (options.environment || 'development') as Environment,
      strict: options.strict ?? false,
      verbose: options.verbose ?? false,
      exitOnError: options.exitOnError ?? true,
    };
  }

  /**
   * Run validation
   */
  async run(): Promise<number> {
    console.log('🔍 Configuration Validation CLI\n');

    // Load and validate config
    const config = this.loadConfig();
    if (!config) {
      return 1;
    }

    // Validate configuration
    const validator = new ConfigValidator(
      this.options.environment,
      this.options.strict
    );
    const result = validator.validate(config);

    // Report results
    this.reportResults(result);

    // Check for security issues
    const securityIssues = this.checkSecurityIssues();
    if (securityIssues > 0) {
      console.error(`\n❌ Found ${securityIssues} security issue(s)\n`);
      return this.options.exitOnError ? 1 : 0;
    }

    // Return exit code
    if (!result.valid) {
      console.error('\n❌ Configuration validation failed\n');
      return this.options.exitOnError ? 1 : 0;
    }

    if (result.warnings && result.warnings.length > 0) {
      console.warn('\n⚠️  Configuration validated with warnings\n');
      return 0;
    }

    console.log('\n✅ Configuration validation passed\n');
    return 0;
  }

  /**
   * Load configuration from env file
   */
  private loadConfig(): any {
    const envFile = this.getEnvFile();

    if (!fs.existsSync(envFile)) {
      console.error(`❌ Environment file not found: ${envFile}`);
      return null;
    }

    // Parse .env file
    const envContent = fs.readFileSync(envFile, 'utf-8');
    const env = this.parseEnvFile(envContent);

    // Build config object
    const config = {
      api: {
        baseUrl: env.VITE_API_BASE_URL || 'http://localhost:8000',
        timeout: 30000,
        apiKey: env.VITE_API_KEY,
      },
      services: {
        grafana: {
          url: env.VITE_GRAFANA_URL || 'http://localhost:3001',
        },
      },
      polling: {
        critical: parseInt(env.VITE_POLLING_INTERVAL_CRITICAL || '3000', 10),
        medium: parseInt(env.VITE_POLLING_INTERVAL_MEDIUM || '5000', 10),
      },
      app: {
        version: '1.0.0',
        environment: this.options.environment,
      },
    };

    if (this.options.verbose) {
      console.log('📋 Loaded configuration:');
      console.log(JSON.stringify(config, null, 2));
      console.log();
    }

    return config;
  }

  /**
   * Get environment file path
   */
  private getEnvFile(): string {
    const envMap: Record<Environment, string> = {
      development: '.env',
      staging: '.env.staging',
      production: '.env.production',
    };

    return path.join(
      process.cwd(),
      envMap[this.options.environment]
    );
  }

  /**
   * Parse .env file
   */
  private parseEnvFile(content: string): Record<string, string> {
    const env: Record<string, string> = {};

    content.split('\n').forEach((line) => {
      // Skip comments and empty lines
      if (line.trim().startsWith('#') || !line.trim()) {
        return;
      }

      const [key, ...valueParts] = line.split('=');
      if (key && valueParts.length > 0) {
        env[key.trim()] = valueParts.join('=').trim();
      }
    });

    return env;
  }

  /**
   * Report validation results
   */
  private reportResults(result: any): void {
    // Report errors
    if (result.errors && result.errors.length > 0) {
      console.error('❌ Validation Errors:\n');
      result.errors.forEach((error: any) => {
        const severity = this.getSeverityIcon(error.severity);
        console.error(`  ${severity} ${error.path}`);
        console.error(`     ${error.message}`);
        console.error(`     Rule: ${error.rule}\n`);
      });
    }

    // Report warnings
    if (result.warnings && result.warnings.length > 0) {
      console.warn('⚠️  Validation Warnings:\n');
      result.warnings.forEach((warning: any) => {
        const severity = this.getSeverityIcon(warning.severity);
        console.warn(`  ${severity} ${warning.path}`);
        console.warn(`     ${warning.message}`);
        console.warn(`     Rule: ${warning.rule}\n`);
      });
    }

    // Summary
    const errorCount = result.errors?.length || 0;
    const warningCount = result.warnings?.length || 0;

    console.log('📊 Summary:');
    console.log(`   Errors: ${errorCount}`);
    console.log(`   Warnings: ${warningCount}`);
    console.log(`   Environment: ${this.options.environment}`);
    console.log(`   Strict Mode: ${this.options.strict ? 'Yes' : 'No'}`);
  }

  /**
   * Check for security issues in files
   */
  private checkSecurityIssues(): number {
    let issues = 0;

    console.log('\n🔐 Security Checks:\n');

    // Check for hardcoded secrets in .env
    if (fs.existsSync('.env')) {
      const envContent = fs.readFileSync('.env', 'utf-8');

      // Check for weak API keys
      if (
        /VITE_API_KEY\s*=\s*(['"]?)(your_api_key|example|test|dev-key|demo)/i.test(
          envContent
        )
      ) {
        console.error(
          '  ❌ Weak or example API key found in .env file'
        );
        issues++;
      }

      // Check for committed .env
      if (!this.isGitIgnored('.env')) {
        console.warn(
          '  ⚠️  .env file should be in .gitignore'
        );
        issues++;
      }
    }

    // Check for HTTP in production
    if (this.options.environment === 'production') {
      const envFile = this.getEnvFile();
      if (fs.existsSync(envFile)) {
        const content = fs.readFileSync(envFile, 'utf-8');
        if (/VITE_.*URL\s*=\s*http:\/\/(?!localhost)/i.test(content)) {
          console.error(
            '  ❌ HTTP URLs found in production config'
          );
          issues++;
        }
      }
    }

    if (issues === 0) {
      console.log('  ✅ No security issues found');
    }

    return issues;
  }

  /**
   * Check if file is in .gitignore
   */
  private isGitIgnored(filename: string): boolean {
    const gitignorePath = path.join(process.cwd(), '.gitignore');

    if (!fs.existsSync(gitignorePath)) {
      return false;
    }

    const gitignore = fs.readFileSync(gitignorePath, 'utf-8');
    return gitignore.split('\n').some((line) => line.trim() === filename);
  }

  /**
   * Get severity icon
   */
  private getSeverityIcon(severity: string): string {
    const icons: Record<string, string> = {
      critical: '🔴',
      high: '🟠',
      medium: '🟡',
      low: '🟢',
    };
    return icons[severity] || '⚪';
  }
}

// CLI execution
async function main() {
  const args = process.argv.slice(2);

  const options: Partial<ValidationOptions> = {
    environment: 'development' as Environment,
    strict: false,
    verbose: false,
    exitOnError: true,
  };

  // Parse arguments
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    switch (arg) {
      case '--env':
      case '-e':
        options.environment = args[++i] as Environment;
        break;
      case '--strict':
      case '-s':
        options.strict = true;
        break;
      case '--verbose':
      case '-v':
        options.verbose = true;
        break;
      case '--no-exit':
        options.exitOnError = false;
        break;
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
        break;
    }
  }

  const cli = new ConfigValidationCLI(options);
  const exitCode = await cli.run();
  process.exit(exitCode);
}

function printHelp() {
  console.log(`
Configuration Validation CLI

Usage: validate-config [options]

Options:
  -e, --env <environment>    Environment to validate (development|staging|production)
                             Default: development
  -s, --strict               Enable strict mode (fail fast on schema errors)
  -v, --verbose              Enable verbose output
      --no-exit              Don't exit with error code on failure
  -h, --help                 Show this help message

Examples:
  # Validate development config
  npm run validate-config

  # Validate production config in strict mode
  npm run validate-config -- --env production --strict

  # Verbose validation for staging
  npm run validate-config -- --env staging --verbose
`);
}

// Run if this is the main module (ES module check)
const isMainModule = import.meta.url === `file://${process.argv[1]}`;

if (isMainModule) {
  main().catch((error) => {
    console.error('❌ Validation failed:', error);
    process.exit(1);
  });
}

export { ConfigValidationCLI };
