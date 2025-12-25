# Copilot Instructions Update Summary

## Overview
Updated `.github/copilot-instructions.md` to provide clear, actionable guidance for AI coding agents working on the Finance Feedback Engine 2.0 codebase.

## Key Changes

### Format Improvements
- **Fixed nesting issue**: Removed unnecessary outer code block markers that were causing formatting problems
- **Cleaner markdown**: Properly formatted all sections with consistent heading levels
- **Better readability**: Improved line breaks and section spacing for easier scanning

### Content Updates
- **Version sync**: Updated from v2.0.0 to v0.9.9 (matches actual `pyproject.toml`)
- **Subsystem count**: Changed from "8 subsystems" to "10+ subsystems" to reflect current architecture
- **Async patterns**: Added explicit mention of async-first design and aiohttp session management
- **Observability**: Added OpenTelemetry metrics and error tracking to architectural overview
- **Portfolio dashboard**: Explicitly called out Rich TUI monitoring features

### Enhanced Sections

#### Big Picture Architecture
- Clarified async/await usage in trading loop
- Documented circuit breaker integration with async execute methods
- Added observability patterns (OpenTelemetry, audit trails)

#### Key Files & Responsibilities
- Expanded descriptions with specific implementation details
- Separated decision engine from ensemble (both critical components)
- Added decision_validation.py explicitly
- Documented learning/feedback analyzer integration
- Clarified optimization module (Optuna-based parameter search, Kelly allocation)

#### Developer Workflows
- Reorganized commands by task (Analysis, Trading, Monitoring, etc.)
- Added explicit examples for each workflow category
- Included both basic and advanced command variations
- Documented optional web service setup

#### Project Conventions
- **Decision JSON Schema**: Added complete schema example with all required fields
- **Position Sizing Formula**: Explicit mathematical formula
- **Ensemble Fallback Tiers**: Clear 5-level hierarchy (Primary → Quaternary)
- **Config Loading**: Documented 3-level precedence order

#### Risk Management Summary
- Clear VaR calculation methodology (95% confidence, 252-day window)
- Correlation analysis triggers and thresholds
- Position concentration limits (30% per asset, 40% per sector)

#### Common Pitfalls & Solutions
- Converted from prose to table format for quick reference
- Covered 8 common issues with specific solutions
- Included exact commands for troubleshooting

#### Editing Safety Rules
- Documented pre-commit validation checklist
- Specified coverage requirements (70% minimum)
- Listed critical guardrails (debate mode, circuit breaker, etc.)
- Added specific test commands for different change types

### New Sections Maintained
- Web Service & Approval Workflows (Telegram + Redis)
- Dashboard & Monitoring (Rich TUI features)
- Integration & Extension Patterns (adding platforms, providers, etc.)
- Related Documentation (links to detailed guides)

## Files Modified
- `.github/copilot-instructions.md`: 374 lines (282 insertions, 278 deletions)

## Validation Checklist

✅ Version number matches project version (0.9.9)
✅ All 10+ subsystems documented with file locations
✅ Critical patterns documented (standardize_asset_pair, circuit breaker, kill-switch)
✅ Safety constraints explicitly listed
✅ Test commands provided for all change types
✅ JSON schema examples included
✅ Configuration precedence documented
✅ Debugging tips provided with exact commands
✅ Related documentation cross-referenced
✅ No formatting issues or nested code blocks

## Key Conventions to Remember

1. **Always standardize asset pairs** before routing or storage
2. **Never disable debate mode in live trading** (testing only)
3. **Max 2 concurrent trades** (hard limit in TradeMonitor)
4. **70% test coverage required** (enforced in pyproject.toml)
5. **Circuit breaker on all platform execute methods** (5 failures → 60s cooldown)
6. **Decision cache can get stale** (clear with `rm data/backtest_cache.db`)
7. **Signal-only mode activates when balance unavailable** (automatic fallback)
8. **Ensemble metadata enrichment** on all decisions (providers, weights, debate summary)

## Agent Usage Tips

- Use this document as your source of truth for project-specific patterns
- Reference specific files when implementing changes
- Follow the "Editing Safety Rules" section before making commits
- Run the exact test commands listed for different change types
- Check "Common Pitfalls & Solutions" when debugging issues
- Validate decision JSON against the provided schema

## What the Existing Instructions Already Covered Well

- Clear data flow diagram (remained unchanged)
- Comprehensive command reference for all CLI operations
- Detailed config loading hierarchy
- Risk management patterns (VaR, correlation, concentration)
- Integration patterns (adding platforms, providers, etc.)
- Backtesting workflow documentation
- Telegram approval flow details

## Next Steps for Agents

1. Read the architecture section to understand overall flow
2. Identify the key files involved in your task
3. Check the conventions section for project-specific patterns
4. Follow the editing rules before making changes
5. Run appropriate tests from the testing section
6. Reference the troubleshooting guide if issues arise

---

**Document Generated**: December 25, 2025
**Version**: 0.9.9
**Last Updated**: December 2025
