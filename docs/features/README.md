# Features Documentation - Finance Feedback Engine 2.0

## Introduction

This directory provides detailed documentation for the various features implemented in the Finance Feedback Engine 2.0. These documents aim to explain the purpose, functionality, architecture, and usage of each key feature.

## AI Integration

The Finance Feedback Engine leverages various AI capabilities for intelligent trading decisions.

*   **AI Provider Options**: Comprehensive details on available AI providers, including Qwen CLI, Gemini CLI, Codex CLI, GitHub Copilot CLI, Local LLM (Ollama), and the "All Local LLMs" ensemble option. This guide covers their advantages, installation, usage, and a detailed comparison.
*   **Local LLM Deployment Guide**: Explains the automatic local LLM deployment feature, which uses Llama-3.2-3B-Instruct via Ollama for privacy, cost-effectiveness, and high-quality local analysis. Includes details on installation, usage, fallback behavior, system requirements, and troubleshooting.
*   **Dynamic Weight Adjustment in Ensemble Mode**: Describes how the ensemble system dynamically adjusts AI provider weights to ensure robust decision-making even when some providers fail. This includes the mechanism of weight renormalization, configuration, metadata, and benefits like resilience and transparency.
*   **Long-Term Portfolio Performance Integration**: Details how long-term portfolio performance metrics (e.g., realized P&L, win rate, Sharpe ratio over 90 days) are automatically included in AI decision-making context, providing models with a comprehensive view of portfolio health.

For more details, see:
*   [AI Provider Options](AI_PROVIDERS.md)
*   [Local LLM Deployment Guide](LOCAL_LLM_DEPLOYMENT.md)
*   [Dynamic Weight Adjustment in Ensemble Mode](DYNAMIC_WEIGHT_ADJUSTMENT.md)
*   [Long-Term Portfolio Performance Integration](LONG_TERM_PERFORMANCE.md)

## Trading Mechanics

These features focus on the core trading operations and risk management.

*   **Autonomous Trading Agent**: Outlines the design and implementation of the fully autonomous trading agent, built as a robust state machine (`IDLE`, `PERCEPTION`, `REASONING`, `RISK_CHECK`, `EXECUTION`, `LEARNING`) to handle the complexities of live trading.
*   **Backtesting (Experimental)**: Provides a minimal framework for simulating a Simple Moving Average (SMA) crossover strategy, enabling early validation of trading ideas. Includes configuration, usage, metrics, and an experimental pseudo-RL ensemble weight strategy.
*   **Live Trade Monitoring System**: Describes the system that automatically detects, tracks, and analyzes open trades in real-time, providing comprehensive metrics and integrating with the ML feedback loop.
*   **Asset Pair Input Validation**: Details how the system automatically standardizes asset pair inputs (e.g., `BTC-USD` to `BTCUSD`) to ensure compatibility with APIs like Alpha Vantage, providing user convenience and error prevention.
*   **RiskGatekeeper Configuration**: Explains the configurable risk management parameters for the trading agent, such as `correlation_threshold`, `max_correlated_assets`, `max_var_pct`, and `var_confidence`.

For more details, see:
*   [Autonomous Trading Agent](AUTONOMOUS_TRADING.md)
*   [Backtesting (Experimental)](BACKTESTING.md)
*   [Live Trade Monitoring System](LIVE_TRADE_MONITORING.md)
*   [Asset Pair Input Validation](ASSET_PAIR_VALIDATION.md)
*   [RiskGatekeeper Configuration](RISK_GATEKEEPER_CONFIG.md)

## Platform & Portfolio

These features enhance interaction with trading platforms and provide a unified view of the portfolio.

*   **Oanda Forex Trading Integration**: Details the integration with Oanda for real-time forex trading, including portfolio tracking, margin management, and automated trade execution.
*   **Platform Switching Guide**: A quick reference for switching between Coinbase Advanced (crypto) and Oanda (forex) platforms, explaining configuration, differences, and common issues.
*   **Portfolio Dashboard**: Explains how the Portfolio Dashboard aggregates portfolio metrics from multiple trading platforms into a unified, comprehensive view.
*   **Portfolio Tracking Feature**: Describes the real-time futures trading portfolio tracking from Coinbase Advanced, providing the AI with context-aware recommendations based on active long/short positions.
*   **Coinbase Spot Balance Integration**: Details the enhanced Coinbase platform integration to check and aggregate spot USD/USDC balances alongside futures data, providing a complete view of all available funds.

For more details, see:
*   [Oanda Forex Trading Integration](OANDA_INTEGRATION.md)
*   [Platform Switching Guide](PLATFORM_SWITCHING.md)
*   [Portfolio Dashboard](PORTFOLIO_DASHBOARD.md)
*   [Portfolio Tracking Feature](PORTFOLIO_TRACKING.md)
*   [Coinbase Spot Balance Integration](SPOT_BALANCE_INTEGRATION.md)

## CLI & Configuration

These documents cover the command-line interface and configuration management.

*   **CLI Behavior Reference**: Provides actual observed behavior for all CLI commands, including expected output formats, command status, execution times, and exit codes.
*   **Config Precedence**: Explains the tiered precedence for loading configuration, from environment variables to `config.local.yaml` and `config.yaml` defaults.

For more details, see:
*   [CLI Behavior Reference](CLI_BEHAVIOR_REFERENCE.md)
*   [Config Precedence](CONFIG_PRECEDENCE.md)

## Integrations

These features describe key integrations with external systems or advanced analytical capabilities.

*   **Multi-Timeframe Pulse System**: Details the system for multi-timeframe technical analysis across multiple timeframes and indicators, automatically injecting comprehensive data into AI trading decisions for improved quality.
*   **Telegram Approval Workflow - Architectural Overview**: Explains the optional web service layer for human-in-the-loop trading approvals via Telegram, enabling users to review and approve/reject AI trading decisions from their mobile device.

For more details, see:
*   [Multi-Timeframe Pulse System](MULTI_TIMEFRAME_PULSE.md)
*   [Telegram Approval Workflow - Architectural Overview](TELEGRAM_APPROVAL_WORKFLOW.md)
