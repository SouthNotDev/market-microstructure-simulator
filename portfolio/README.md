# Quantitative Research Portfolio

**Independent research in prediction markets, systematic trading infrastructure, and financial market microstructure.**

This page documents selected projects by SouthNotDev. Some research implementations are maintained in **private source repositories**. The summaries below are public so that reviewers can evaluate the research questions, methodological choices, and engineering scope without receiving access to private code, datasets, trading accounts, or credentials.

## Selected projects

### 1. PolyTest | Prediction Market Backtesting & Execution Research
**Research platform | Python | Event-driven systems | Polymarket**

[Read the public project overview](./polytest/README.md)

A research testbed with Polymarket data connectors, deterministic historical simulation, paper trading, live dry-run workflows, and reproducibility checks. Methodological emphasis: timestamp-aware data access, prevention of look-ahead bias, realistic execution assumptions, and reproducible results.

**Source:** Private. The linked overview contains documentation only.

### 2. Polymarket Insiders | Trader Signals & Forecast Aggregation
**Quantitative research | Python | Monte Carlo | FastAPI | Next.js**

[Read the public project overview](./polymarket-insiders/README.md)

An end-to-end research system for studying prediction-market participant behavior. Includes wallet-level data processing, trader ranking features, simulations of weighting schemes, event-level consensus estimates, validation workflows, and a visualization interface.

**Source:** Private. The linked overview contains documentation only.

### 3. Market Microstructure Simulator
**Open-source implementation | Python | Limit order books | Matching engines**

[Explore the project, code, tests, and live visualization](../README.md)

A standalone, learning-first market simulator implementing price-time priority, partial fills, order cancellations, market/limit orders, and synthetic order flow. This project **does** have public source code and a dashboard.

### 4. Daily USD/COP Market Briefings
**Public project | Python | Financial data pipelines | LLM-assisted reporting**

[Explore the public repository](https://github.com/SouthNotDev/Correlation_DailyUpdate_USD-COP)

A data-driven workflow for researching USD/COP movements and producing recurring market briefings using cleaned financial data, statistical checks, and structured narrative generation.

## Research approach

- **Data provenance:** distinguish market observations from inferred information and post-event data.
- **Backtest integrity:** preserve information availability at the simulated decision time and test timing assumptions.
- **Execution realism:** account for bid-ask spreads, available book depth, partial fills, fees, and slippage.
- **Reproducibility:** define data contracts, deterministic fixtures, explicit configurations, and testable outputs.
- **Evidence over headline returns:** communicate research limits and distinguish predictive skill from realized trading performance.

## Source-code availability

Private-source projects are intentionally represented by public, documentation-only project pages. Their **original GitHub repositories remain private**, and the public pages are not mirrors of the source code. The absence of public source should not be interpreted as third-party verification of the projects or their results.

For professional inquiries, contact the repository owner through GitHub.
