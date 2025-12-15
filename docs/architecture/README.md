# Finance Feedback Engine 2.0 Architecture

## Introduction

The Finance Feedback Engine 2.0 is built on a modular, scalable architecture designed for real-time trading decisions, backtesting, and performance analysis. The system is composed of several key components, each with a specific responsibility. This document provides a high-level overview of the architecture.

## Data Pipeline Architecture

The data pipeline is a production-grade system for ingesting, transforming, and serving market data, AI decisions, and trade executions. It follows a Lakehouse architecture (Unified Batch + Streaming) with Bronze, Silver, and Gold layers.

*   **Bronze Layer:** Raw, immutable data from various sources.
*   **Silver Layer:** Cleaned, enriched, and curated data.
*   **Gold Layer:** Business-level aggregations and metrics for analysis.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA SOURCES                                    │
├─────────────────┬────────────────┬─────────────────┬───────────────────┤
│ Alpha Vantage   │ Coinbase API   │ Oanda API       │ Trading Platforms │
│ (Multi-TF OHLC) │ (Crypto Data)  │ (Forex Data)    │ (Trade Executions)│
└────────┬────────┴────────┬───────┴────────┬────────┴──────────┬────────┘
         │                 │                │                   │
         ▼                 ▼                ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                                   │
├──────────────────────────────┬──────────────────────────────────────────┤
│  Batch Ingestion             │  Streaming Ingestion                     │
│  ├─ Historical Backfill      │  ├─ Real-time Market Data (WebSocket)   │
│  ├─ Daily OHLC Snapshots     │  ├─ Trade Executions (Event Stream)     │
│  └─ Sentiment/Macro Updates  │  └─ Live P&L Updates                    │
└──────────────────────────────┴──────────────────────────────────────────┘
```

For more details, see the [full data pipeline architecture documentation](DATA_PIPELINE_ARCHITECTURE.md).

## Decision Engine Architecture

The Decision Engine is responsible for generating trading decisions. It is composed of four specialized classes:

*   `PositionSizingCalculator`: Calculates position sizes based on risk management.
*   `AIDecisionManager`: Handles AI provider selection and communication.
*   `MarketAnalysisContext`: Prepares market data and context for decision making.
*   `DecisionValidator`: Validates decisions before execution.

For more details, see the [full decision engine architecture documentation](DECISION_ENGINE_ARCHITECTURE.md).

## Ensemble System Architecture

The ensemble system combines multiple AI providers to generate more robust and reliable trading recommendations. It features:

*   Dynamic weight adjustment to handle provider failures.
*   Multiple voting strategies (weighted, majority, stacking).
*   Adaptive learning to improve provider weights based on performance.
*   A 4-tier progressive fallback system to ensure decisions are always generated.

```
┌───────────────────────────────────────────────────────────────────────┐
│ Tier 1: PRIMARY STRATEGY                                              │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: As configured (weighted/majority/stacking)                  │
│ Requirements: At least 1 valid provider                               │
│ Quality: ★★★★★ (Best)                                                 │
└───────────────────────────────────────────────────────────────────────┘
                                     ↓
┌───────────────────────────────────────────────────────────────────────┐
│ Tier 2: MAJORITY VOTING FALLBACK                                      │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: Simple vote counting (1 vote per provider)                  │
│ Requirements: At least 2 valid providers                              │
│ Quality: ★★★★☆ (Good)                                                 │
└───────────────────────────────────────────────────────────────────────┘
                                     ↓
┌───────────────────────────────────────────────────────────────────────┐
│ Tier 3: SIMPLE AVERAGING FALLBACK                                     │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: Average all confidences and amounts                         │
│ Requirements: At least 2 valid providers                              │
│ Quality: ★★★☆☆ (Acceptable)                                           │
└───────────────────────────────────────────────────────────────────────┘
                                     ↓
┌───────────────────────────────────────────────────────────────────────┐
│ Tier 4: SINGLE PROVIDER FALLBACK                                      │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: Use highest confidence provider as sole decision maker      │
│ Requirements: At least 1 valid provider                               │
│ Quality: ★★☆☆☆ (Degraded - Last Resort)                              │
└───────────────────────────────────────────────────────────────────────┘
```

For more details, see the [full ensemble system documentation](ENSEMBLE_SYSTEM.md) and the [visual fallback system documentation](ENSEMBLE_FALLBACK_VISUAL.md).

## Multi-Timeframe Feature Pulse Architecture

This system enhances the trading engine with comprehensive multi-timeframe technical analysis, including indicators like RSI, MACD, Bollinger Bands, ADX, and ATR. The "feature pulse" is integrated into the `DecisionEngine` to provide AI models with a richer context for their decisions.

For more details, see the [full multi-timeframe feature pulse architecture documentation](MULTI_TIMEFRAME_PULSE_DESIGN.md).
