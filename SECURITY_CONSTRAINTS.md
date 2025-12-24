# Security Constraints

This file defines minimum versions of security-sensitive packages to prevent known vulnerabilities.

## Purpose

During CI/CD security scans, this file ensures that:
1. No vulnerable versions of dependencies can be installed
2. Transitive dependencies meet minimum security requirements
3. Future dependency updates maintain security baselines

## Usage

```bash
# Install with constraints
pip install -c constraints.txt .

# Install dev dependencies with constraints
pip install -c constraints.txt .[dev]

# Install pipeline dependencies with constraints
pip install -c constraints.txt .[pipeline]
```

## Maintaining This File

When security vulnerabilities are discovered:

1. Identify the vulnerable package and version
2. Add or update the constraint to require the fixed version
3. Document the CVE/vulnerability ID in a comment
4. Test the installation with the updated constraints

## Current Constraints

- **twisted>=24.7.0rc1** - Fixes CVE-2024-41671 and PYSEC-2024-75
  - CVE-2024-41671: HTTP pipelining vulnerability
  - PYSEC-2024-75: HTML injection in redirect URLs

- **certifi>=2024.7.4** - Latest root certificate bundle
- **urllib3>=2.3.0** - Security fixes for HTTP handling
- **requests>=2.32.3** - Security improvements in HTTP library
- **cryptography>=42.0.0** - Critical cryptographic fixes
- **jinja2>=3.1.6** - Template security fixes
