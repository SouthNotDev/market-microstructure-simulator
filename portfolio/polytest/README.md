# PolyTest

**Prediction Market Research, Backtesting & Execution Infrastructure**

**Status:** Research / engineering project  
**Implementation:** Private GitHub repository. **This public page contains no source code, private datasets, API credentials, or account information.**

## Objective

Build a reproducible framework for studying systematic strategies in event-contract markets, with particular focus on separating statistical signals from the effects of execution costs, data availability, and simulation assumptions.

## Research and engineering scope

- **Market discovery and ingestion:** connectors for Polymarket Gamma metadata, CLOB REST/WebSocket streams, and historical trades via supported data sources.
- **Canonical event model:** normalize market, trade, order-book, and execution messages into consistent research interfaces.
- **Historical simulation:** event-driven backtests with deterministic event ordering and a simulated execution broker.
- **Information-timing controls:** as-of data access and explicit safeguards against look-ahead bias.
- **Execution assumptions:** analysis of limit order book availability, bid/ask spreads, partial fills, slippage, and fee sensitivity.
- **Paper and dry-run workflows:** reuse research strategy interfaces across simulated and non-trading validation modes.
- **Testing and reproducibility:** fixtures, smoke tests, deterministic manifests, replay checks, and acceptance scenarios.

## Architecture, conceptually

1. Collect market metadata and timestamped observations.
2. Normalize input data into canonical market and execution events.
3. Supply data to strategy logic through a time-aware feed.
4. Translate strategy decisions into order intents.
5. Simulate or validate broker behavior, including partial fills and trading frictions.
6. Produce structured reports and reproducibility manifests.

The original codebase separates data connectors, feeds, strategy runners, broker abstractions, operational controls, risk checks, and reporting.

## Research principles

### 1. No future information in historical signals
Features should be computed from information actually available at each decision timestamp, not from final market outcomes or retrospectively corrected observations.

### 2. Price is not the same as executable opportunity
Displayed midpoints or theoretical fair values do not imply executable prices. Strategies need to be tested against spread, depth, fees, and fill assumptions.

### 3. A positive backtest is not evidence of tradable alpha by itself
Evaluation should account for data quality, timing, execution, sensitivity to assumptions, and genuine out-of-sample performance.

## Project boundaries

This is a research infrastructure project, not a public audited performance record. No live-investment returns, verified alpha, or profitability claims are made in this page.

## Access

The implementation and research data remain private. This page exists to describe the project for technical review, recruiting, and professional portfolio use.

[Back to research portfolio](../README.md)
