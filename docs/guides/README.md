# Guides and Quick Starts - Finance Feedback Engine 2.0

## Introduction

This directory contains various guides and quick-start documents to help users understand, deploy, and utilize the Finance Feedback Engine 2.0 effectively. These guides cover topics ranging from automated refactoring and deployment to data pipeline management and integration with external services like Telegram.

## Automated Refactoring

The Finance Feedback Engine 2.0 incorporates a robust automated refactoring framework designed to iteratively improve code quality and performance.

*   **Automated Refactoring Quick Start**: Get started with automated, measured refactoring in under 10 minutes, including benchmarking, dry runs, and configuration optimization.
*   **Automated Refactoring Framework**: A detailed overview of the framework's architecture, components (RefactoringTask, PerformanceTracker, RefactoringOrchestrator, AgentConfigOptimizer), usage patterns, configuration options, and safety features like automatic rollback and Git integration.

For more details, see the [Automated Refactoring Quick Start](AUTOMATED_REFACTORING_QUICKSTART.md) and the [Automated Refactoring Framework](AUTOMATED_REFACTORING.md).

## Deployment Guides

These guides provide comprehensive instructions for deploying and managing the Finance Feedback Engine in various environments.

*   **Automatic Local LLM Deployment**: Explains the fully automatic local LLM deployment feature, including Ollama installation, model downloading, platform support (Linux, macOS, Windows), model selection research, and fallback strategies.
*   **Deployment Guide**: A comprehensive guide covering environment variables, Docker and cloud deployment (AWS EC2, GCP, Azure), configuration management, security best practices, and monitoring & logging.
*   **DevOps Deployment Guide**: Provides detailed instructions and considerations for deploying the Finance Feedback Engine in a DevOps environment.
*   **DevOps Quick Start - Cheat Sheet**: A fast reference for deploying and managing the engine with one-command deployment, bot control, monitoring access, key API endpoints, Prometheus metrics, alert examples, Docker quick reference, common tasks, important files, environment setup, and security checklist.

For more details, see:
*   [Automatic Local LLM Deployment](AUTOMATIC_DEPLOYMENT.md)
*   [Deployment Guide](DEPLOYMENT.md)
*   [DevOps Deployment Guide](DEVOPS_DEPLOYMENT.md)
*   [DevOps Quick Start - Cheat Sheet](DEVOPS_QUICKSTART.md)

## Data Pipeline

*   **Data Pipeline Quick Start Guide**: This guide walks you through setting up and running the Finance Feedback Engine data pipeline locally in under 30 minutes. It covers the Bronze, Silver, and Gold layers, prerequisites, backfilling historical data, verifying data in Delta Lake, and querying historical data.

For more details, see the [Data Pipeline Quick Start Guide](DATA_PIPELINE_QUICKSTART.md).

## Testing & Mocking

*   **MockLiveProvider Guide**: Explains how to use `MockLiveProvider` to simulate live data streaming using historical data, essential for realistic backtesting without looking ahead. It covers creating the provider, streaming data, advanced features like historical windows and peeking ahead, and integration with backtesting.
*   **MockTradingPlatform Usage Guide**: A comprehensive guide to `MockTradingPlatform`, simulating real trading behavior without actual API calls. It covers features like full state tracking, slippage and fees simulation, position management, and backtesting workflows.

For more details, see the [MockLiveProvider Guide](MOCK_LIVE_PROVIDER_GUIDE.md) and the [MockTradingPlatform Usage Guide](MOCK_PLATFORM_GUIDE.md).

## Tooling & Utilities

*   **Install Dependencies Command - Quick Reference**: A guide for the `install-deps` command, which helps manage project dependencies by comparing installed packages against `requirements.txt` and offering to install missing ones.

For more details, see the [Install Dependencies Command - Quick Reference](INSTALL_DEPS_COMMAND.md).

## Integrations

*   **Telegram Bot Setup Guide**: A complete guide to setting up the Telegram approval workflow for the Finance Feedback Engine 2.0, covering prerequisites, quick start, detailed setup (with/without Redis), testing, usage examples, troubleshooting, and production deployment.

For more details, see the [Telegram Bot Setup Guide](TELEGRAM_SETUP_GUIDE.md).
