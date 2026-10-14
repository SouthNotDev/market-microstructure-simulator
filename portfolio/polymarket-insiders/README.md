# Polymarket Insiders

**Trader Behavior, Signal Ranking & Forecast Aggregation in Prediction Markets**

**Status:** Quantitative research project  
**Implementation:** Private GitHub repository. **This public page contains no source code, raw account data, credentials, or private research exports.**

## Research question

Can observable participant behavior in prediction markets provide an incremental forecasting signal beyond market-implied prices? If so, how robust is that signal when evaluated outside the original training events and after realistic execution costs?

## Project components

### Data engineering
A Python pipeline extracts and standardizes prediction-market transaction and event data, producing participant-level activity histories and event-level observations.

### Signal construction
Research features include historical prediction accuracy, traded notional, participation consistency, outcome concentration, and timing-related behaviors. Alternative ranking and weighting methods are evaluated rather than relying on a single heuristic.

### Forecast aggregation
A Monte Carlo-driven research module tests different feature-weight combinations, ranks participating accounts, and builds aggregate forecasts from selected participant predictions.

### Validation
The project includes event holdout scenarios and comparisons across candidate weighting methods. The research emphasizes sensitivity to sample choice, multiple-testing concerns, and the distinction between historical fit and future signal value.

### Research interface
An internal visualization interface combines a Python analysis pipeline, FastAPI services, and a Next.js dashboard for inspecting trader-level metrics, event history, model configurations, and consensus outputs.

## Methodological considerations

- **Selection bias:** exceptionally successful wallets may look predictive due to sample selection and survivorship.
- **Information leakage:** only information available at prediction time should determine forecasts.
- **Dependence:** multiple wallets may respond to the same information rather than contributing independent signals.
- **Trading costs and liquidity:** a forecasting advantage does not necessarily survive spread, fees, and execution delay.
- **Out-of-sample testing:** historical rank or model fit alone is insufficient to establish sustainable alpha.

## Research status

The project is exploratory. This overview describes the methodology and implementation scope; it does not claim a statistically validated, net-profitable live strategy. A negative or inconclusive result is considered a legitimate research outcome.

## Access

The implementation and data remain private. This is a documentation-only public project overview intended for professional and technical review.

[Back to research portfolio](../README.md)
