# Market Making And Market Microstructure Simulator

## Project Purpose

This project is a learning-first crypto market making and market microstructure simulator.

The main goal is not to rush toward a polished application. The main goal is to understand, step by step, how electronic markets work internally and how market making strategies are built, tested, measured, and improved.

The simulator should help answer questions such as:

- How does a limit order book actually work?
- How are bids, asks, spread, depth, and queue priority represented in code?
- What happens when market orders, limit orders, and cancellations arrive?
- How does a market maker earn spread?
- Why does inventory risk matter?
- What is adverse selection?
- How do volatility, latency, tick size, fees, and order flow affect profitability?
- How can a strategy look profitable in theory but fail after realistic frictions?

The first target domain is crypto because crypto markets are accessible, data is easier to obtain, and the mechanics are close enough to professional electronic markets to be useful for practice.

## Collaboration Style

This repository should be developed through discussion and learning checkpoints.

Do not jump straight into building large features. Before implementing a new concept, explain the idea in plain language, connect it to market mechanics, and use a small numerical example when helpful.

For each meaningful step:

1. Explain the concept.
2. Show a small concrete example.
3. Ask whether the concept is clear.
4. Discuss design choices for the simulator.
5. Implement only the agreed small piece.
6. Add tests or examples that prove the behavior.
7. Review what was learned before moving on.

The user is knowledgeable in finance, so avoid over-explaining basic finance ideas. Focus more on market mechanics, microstructure details, modeling choices, and how those ideas become code.

## Technical Focus

The project should prioritize:

- Market mechanics over visual design.
- Code clarity over cleverness.
- Small, inspectable modules over large abstractions.
- Deterministic tests before stochastic simulations.
- Realistic crypto exchange constraints when they matter.
- Explicit assumptions instead of hidden behavior.

Visualizations can be added later, but they are not the main focus. If visual output is useful, keep it simple and analytical, such as plots of inventory, PnL, spread, depth, fills, and order flow.

## Initial Implementation Direction

Python is the preferred starting language because it is readable, widely used in quant research, and good for simulation, testing, and later data analysis.

The first serious building block should be a price-time-priority limit order book.

Core concepts to build first:

- Order side: buy or sell.
- Order type: limit order, market order, cancellation.
- Best bid and best ask.
- Bid-ask spread.
- Mid price.
- Resting liquidity.
- Aggressive liquidity-taking orders.
- Passive liquidity-providing orders.
- Price priority.
- Time priority.
- Trade generation from matching.

The first version should be deterministic and simple. It should not start with real exchange data, advanced stochastic models, dashboards, or complex strategy logic.

## Learning Roadmap

The roadmap should evolve through discussion, but a reasonable path is:

1. Limit order book mechanics.
2. Matching engine behavior.
3. Market order flow, limit order flow, and cancellations.
4. Basic market state metrics: spread, mid price, depth, imbalance.
5. Simple market maker that posts bid and ask quotes.
6. Fill simulation and realized PnL.
7. Inventory tracking and inventory risk.
8. Fees, rebates, tick size, lot size, and exchange constraints.
9. Adverse selection and toxic order flow.
10. Latency and queue position.
11. Volatility regimes and order flow regimes.
12. Strategy evaluation metrics.
13. Calibration from crypto exchange data.
14. More advanced models such as Avellaneda-Stoikov or queue-reactive models.

Each roadmap item should become a small milestone only after the previous mechanics are understood.

## Code Design Principles

Prefer domain objects with explicit names:

- `Order`
- `Trade`
- `OrderBook`
- `MatchingEngine`
- `MarketEvent`
- `MarketMaker`
- `Portfolio`
- `Simulation`

Keep the system modular, but do not invent abstractions before they are needed.

Use tests to lock in microstructure behavior. For example:

- A buy market order should match the lowest ask first.
- A sell market order should match the highest bid first.
- Orders at the same price should match FIFO.
- A crossing limit order should execute immediately.
- Unfilled limit quantity should rest on the book.
- Cancelling an order should remove only the intended resting quantity.

Use simple examples before randomized simulations. Randomness should be seeded when used.

## Documentation Style

Documentation should explain both the financial concept and the code representation.

When adding a new module or concept, include:

- What the concept means in market microstructure.
- Why it matters for market making.
- What simplifying assumptions the simulator makes.
- How the code models it.
- A tiny example with numbers.

Avoid treating formulas as magic. If an equation is introduced, explain each variable and the intuition before using it in code.

## Explanation Style After Code Changes

After implementing something, do not give only a short summary such as "I added `OrderBook` and now it works."

The final explanation should walk through the implementation in a way that helps the user learn how the code actually works.

For each meaningful code change, explain:

- Which classes, functions, or files were created or modified.
- What each class or function is responsible for.
- Why that design was chosen for market-mechanics reasons.
- How the important methods work internally.
- What Python structures were used, such as `dict`, `deque`, `dataclass`, `Enum`, properties, or loops.
- How data flows through the code.
- What tests prove the behavior.

Prefer explanations like:

```text
I created `PriceLevel` to represent all resting orders at one price. Internally
it uses a `deque`, which is a queue-like data structure. We append new orders
to the right side of the queue, so older orders stay at the front. That models
FIFO time priority: if two sell orders are both at 100.10, the one that arrived
first will be consumed first by the matching engine later.
```

Do not overwhelm the user with every line of code, but do explain the real mechanics behind the important lines.

If the code uses a Python feature the user may not know, briefly explain the feature in context. For example, if a method uses `setdefault`, explain that it means "get the existing price level if it exists; otherwise create it."

The goal is for the user to understand not only what was built, but how and why it was built that way.

## Current Project Biases

This simulator is not trying to be a production trading system.

It should not handle private keys, live order placement, real capital, or exchange credentials unless the user explicitly changes the project scope later.

The simulator can later ingest public crypto market data, but the early stages should be synthetic and controlled so the mechanics are easy to inspect.

## Working Agreement

Before major changes, discuss the next concept and the smallest useful implementation.

If the user asks to slow down, stop coding and return to explanation.

If a design choice has multiple reasonable options, present the tradeoff instead of silently choosing.

The project succeeds when the user can explain how each part works, why it exists, and how it affects market maker behavior.
