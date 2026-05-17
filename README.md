# Market Microstructure Simulator

A learning-first simulator for crypto market microstructure and market making.

The goal is simple: understand how an electronic market works by building the
parts step by step.

This is not a live trading system. It does not connect to an exchange, place
real orders, or use real money.

## Demo

Live demo:

[https://southnotdev.github.io/market-microstructure-simulator/](https://southnotdev.github.io/market-microstructure-simulator/)

Dashboard only:

[https://southnotdev.github.io/market-microstructure-simulator/dashboard/](https://southnotdev.github.io/market-microstructure-simulator/dashboard/)

<video src="assets/demo.mp4" controls muted loop playsinline width="100%"></video>

If the video does not render in your browser, open the file directly:

[assets/demo.mp4](assets/demo.mp4)

## What The Dashboard Shows

The dashboard shows one simplified market pipeline:

```text
Random agents
    -> Exchange
    -> Matching engine
    -> Limit order book
    -> Recorder
    -> Midprice chart
```

Several synthetic orders move through the system at the same time. Each moving
dot is an order. The dot color identifies the order, and the dot size is based
on order quantity.

The boxes stay neutral on purpose. The colored dots and short colored line
segments show where each order is moving.

## How This Was Built

This project was built as a learning process, not as a finished product.

The process so far:

1. Define the basic market objects.
2. Build orders, trades, and match results.
3. Build a price-time priority order book.
4. Add a matching engine.
5. Add an exchange layer that assigns order IDs.
6. Add a recorder that stores trades and book snapshots.
7. Add a simulation loop.
8. Add simple scripted/random agents.
9. Generate synthetic order flow.
10. Build a visual dashboard from real simulator output.

The dashboard does not invent fake states in the browser. The data comes from
the Python simulator and is exported to:

```text
dashboard/trace.json
```

## Main Concepts

The simulator currently covers:

- Limit orders
- Market orders
- Cancellations
- Resting liquidity
- Aggressive liquidity
- Best bid and best ask
- Spread
- Midprice
- Price-time priority
- Partial fills
- IOC and FOK behavior
- Book snapshots
- Trade logs
- Synthetic order flow

## Project Structure

```text
src/market_sim/
    domain.py       Basic market objects
    book.py         Limit order book storage
    matching.py     Matching rules
    exchange.py     Exchange gateway and order IDs
    recording.py    Trades and book snapshots
    simulation.py   Event loop
    agents.py       Simple agents

examples/
    dashboard_trace.py      Generates dashboard/trace.json
    scripted_agent_demo.py  Small agent example

dashboard/
    index.html
    styles.css
    app.js
    trace.json

assets/
    demo.mp4        Muted simulator preview

tests/
    Deterministic tests for the simulator mechanics
```

More detailed project notes are in:

```text
STRUCTURE.md
PLAN.md
AGENTS.md
```

## Run Locally

Install the package in editable mode:

```bash
python3 -m pip install -e .
```

Generate the dashboard trace:

```bash
python3 examples/dashboard_trace.py
```

Start a local static server:

```bash
python3 -m http.server 8765
```

Open:

```text
http://127.0.0.1:8765/
```

Or open the dashboard directly:

```text
http://127.0.0.1:8765/dashboard/
```

## Run Tests

```bash
python3 -m pytest
```

The tests are deterministic. They check the market mechanics before adding more
randomness or strategy complexity.

## Current Status

This is an early educational simulator.

The current focus is market mechanics:

- how orders enter the system;
- how the exchange assigns IDs;
- how the matching engine interacts with the book;
- how trades and snapshots are recorded;
- how top-of-book changes move the midprice.

Future work may add inventory, PnL, fees, latency, queue position, and simple
market-making strategies.
