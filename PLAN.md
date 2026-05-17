# Market Making Simulator Plan

## Purpose Of This File

`PLAN.md` is the living plan for the project.

It records:

- What we are building.
- Why each part matters.
- What concepts must be understood before implementation.
- What design decisions we have made.
- What tests or examples prove the behavior.
- What remains open for later discussion.

This file should be updated as the simulator evolves. It is not a frozen specification.

## Project Direction

We are building a learning-first crypto market making and market microstructure simulator.

The focus is:

- Market mechanics.
- Matching engine behavior.
- Limit order book structure.
- Market maker decision logic.
- Inventory, PnL, fees, latency, adverse selection, and realistic frictions.
- Code that makes every concept inspectable.

The focus is not:

- Visual polish.
- Live trading.
- Exchange credentials or real capital.
- A production trading system.

## Core Architecture Decision

The simulator will use **layered components** and later run through an
**event-driven** loop.

The chosen component split is:

```text
domain.py
    Basic market objects: Order, Trade, MatchResult, enums.

book.py
    Stores resting liquidity: bids, asks, price levels, FIFO queues.

matching.py
    Applies exchange rules: matching, partial fills, IOC, FOK, resting leftovers.

simulation.py
    Runs the event loop and coordinates agents, matching, portfolio, and recording.

portfolio.py
    Tracks cash, inventory, fees, and PnL.

agents.py
    Decides what orders to send.

recording.py
    Stores trades, snapshots, and metrics for analysis.
```

Important responsibility split:

```text
OrderBook:
    Stores resting orders and reports book state.
    It does not perform matching.

MatchingEngine:
    Handles all matching rules.
    It uses the OrderBook but owns the execution logic.
```

This keeps storage separate from execution rules.

The simulator itself will be **event-driven**.

Markets change when events happen, such as:

- A limit order arrives.
- A market order arrives.
- A cancellation arrives.
- A trade is created.
- A market maker changes quotes.
- A fee is charged.
- A portfolio changes inventory or cash.

The simulator should process one event at a time.

Basic loop:

```text
while simulation_has_not_finished:
    event = event_source.next_event()
    result = matching_engine.process(event)
    agents.observe(result, order_book)
    actions = agents.decide()
    process_agent_actions(actions)
    recorder.record(current_state)
```

We should not begin with an uncontrolled infinite loop. Instead, the simulator should support clear stopping conditions:

- Run for `N` events.
- Run until a simulated timestamp.
- Run until inventory exceeds a limit.
- Run until loss exceeds a limit.
- Later, optionally run continuously until manually stopped.

## Important Design Decisions So Far

### Market Domain

Initial domain: crypto.

Reason:

- Crypto order books are accessible.
- Public data is easier to obtain later.
- Mechanics are close enough to other electronic markets to be educational.

### Quantity Representation

Quantities should be integers.

For BTC-like examples:

```text
quantity unit = satoshis
1 BTC = 100,000,000 sats
25,000 sats = 0.00025 BTC
```

Reason:

- Avoid floating point precision errors.
- Match how real exchanges use discrete quantity increments.
- Make tests exact.

### Price Representation

Prices should be integer ticks internally.

Example:

```text
tick_size = 0.01 USDT
price_ticks = 10010
display_price = 100.10 USDT
```

Reason:

- Matching depends on exact comparisons.
- Floating point prices can produce precision bugs.
- Tick size is central to real market microstructure.

### Order Instructions

The first implementation should support:

- Regular limit orders.
- Market orders.
- IOC: immediate-or-cancel.
- FOK: fill-or-kill.

Reason:

- Regular limit orders force us to model resting liquidity and queue priority.
- IOC and FOK are useful but can be built around the same matching logic.
- Supporting them early clarifies how aggressive orders differ from passive orders.

## Recommended Development Phases

The phases below are intentionally small. Each phase should include discussion, examples, implementation, tests, and review.

## Phase 1: Orders, Trades, And Basic Concepts

### Goal

Define the smallest set of domain objects needed to talk about the market precisely.

### Concepts

- Buy side vs sell side.
- Limit orders.
- Market orders.
- Time in force: regular, IOC, FOK.
- Order IDs.
- Quantities in sats.
- Prices in ticks.
- Trades as the output of matching.

### Why This Comes First

Before building the order book, we need clear data structures. Bad early representations create confusion later.

### Likely Objects

- `Side`
- `OrderType`
- `TimeInForce`
- `Order`
- `Trade`

### Testing

Use simple unit tests:

- An order stores side, quantity, price, and time-in-force correctly.
- Market orders do not require a limit price.
- Limit orders require a limit price.
- Quantity must be positive.
- Price ticks must be positive when present.

### Learning Checkpoint

The user should be able to explain:

- Why we use integer sats instead of float BTC.
- Why we use integer price ticks instead of float USDT prices.
- The difference between order type and time-in-force.

## Phase 2: Limit Order Book Storage

### Goal

Build the data structure that stores resting liquidity.

### Concepts

- Bid side and ask side.
- Best bid and best ask.
- Spread.
- Mid price.
- Price levels.
- FIFO queue at each price level.
- Resting liquidity.

### Why This Comes Second

The order book must be able to store passive orders before we can correctly match aggressive orders.

### Likely Objects

- `OrderBook`
- `PriceLevel`
- `BookOrder`

### Order Vs BookOrder Decision

The original `Order` object is immutable historical input.

The `BookOrder` object is live/open book state.

Reason:

- We should not mutate the original submitted order quantity after fills.
- The book still needs a mutable `remaining_quantity`.
- Fully filled or canceled `BookOrder` objects should be removed from the book.
- The book should contain only live resting liquidity, not dead historical orders.

`BookOrder` lives in `book.py` because it is internal order book state, not an
incoming exchange message.

### Testing

Use deterministic unit tests:

- Adding a buy limit below the ask rests on the bid side.
- Adding a sell limit above the bid rests on the ask side.
- Best bid is the highest bid price.
- Best ask is the lowest ask price.
- Spread is best ask minus best bid.
- Orders at the same price preserve arrival order.
- Adding a resting order creates a `BookOrder`.
- Depth sums live `remaining_quantity`.
- Peeking at the best order does not remove liquidity.
- Removing the best order preserves FIFO and deletes empty price levels.

### Book Consumption API

Before implementing the matching engine, the book should expose controlled
methods for consumption:

- `best_price_for_side(side)`
- `best_level_for_side(side)`
- `peek_best_order(side)`
- `remove_best_order(side)`

Reason:

- The matching engine should not directly edit `bids`, `asks`, or raw queues.
- Peeking and removal should preserve price-time priority.
- Empty price levels should be cleaned up by the book.
- Matching logic should stay focused on execution rules, not storage details.

### Cancellation Decision

Cancellation should begin as full cancellation only:

```text
cancel_order(order_id)
```

If the order is live, remove all remaining quantity. If it is not live, return
`None`.

The book should keep a secondary index:

```text
orders_by_id: order_id -> BookOrderLocation(side, price_ticks)
```

Reason:

- Matching is optimized by price queues.
- Cancellation is optimized by order ID lookup.
- Without an index, cancellation would need to scan every price level.
- The book must remove an order from both the FIFO queue and the index.
- Empty price levels should still be deleted.

### Order ID Decision

Low-level tests can still pass order IDs manually when constructing `Order`
objects directly.

For simulator usage, order ID generation now lives in the `Exchange` gateway.

Likely future direction:

- `Order` stores an already assigned ID.
- The exchange/simulation boundary generates IDs.
- The book uses IDs for cancellation and trade references.
- Trades reference order IDs but do not generate them.

## Phase 4: Exchange Gateway

### Goal

Create a small exchange-like boundary that assigns order IDs and timestamps.

### Concepts

- Gateway/interface layer.
- Monotonic order IDs.
- Monotonic event timestamps.
- Submit limit order intent.
- Submit market order intent.
- Cancel order intent.
- `CancelResult` receipts.

### Why This Comes After Matching And Cancellation

Before this layer, tests manually constructed `Order` objects with IDs and
timestamps. That is useful for unit tests, but agents and simulations should not
need to manually manage identity and event sequence.

The exchange gateway becomes the boundary where intent becomes an official
market message.

### Likely Objects

- `Exchange`
- `CancelResult`

### Testing

Use deterministic unit tests:

- First submitted order gets order ID 1 and timestamp 1.
- Second submitted order gets order ID 2 and timestamp 2.
- Limit submissions can rest in the book.
- Market submissions can match existing liquidity.
- IOC can be submitted through the gateway.
- Canceling an existing order returns accepted `CancelResult`.
- Canceling a missing order returns rejected `CancelResult`.
- Canceling after partial fill reports remaining live quantity.

### Learning Checkpoint

The user should be able to explain:

- Why ID generation belongs at the exchange boundary.
- Why `Order` stores IDs but does not generate them.
- Why cancel results are event receipts, not just removed book objects.

## Phase 5: Recording

### Goal

Record what happened over time without making `Exchange` responsible for
history.

### Concepts

- Event history.
- Trade log.
- Match result log.
- Cancel result log.
- Book snapshots.
- Top-of-book state.
- Depth by price level.
- Immutable historical records.

### Why This Comes After The Exchange Gateway

Once the exchange can submit and cancel orders, we need a way to inspect many
events over time.

Market making cannot be understood from one fill only. We need history to later
compute fill rate, volume, spread over time, inventory, PnL, and drawdown.

### Design Decision

Recording stays separate from `Exchange`.

Reason:

- `Exchange` changes market state.
- `Recorder` observes and stores history.
- A later simulation loop can coordinate both.
- Tests can use the exchange without always recording.

### Likely Objects

- `BookSnapshot`
- `Recorder`

### Testing

Use deterministic unit tests:

- Recording a match stores the result.
- Recording a match stores trades from the result.
- Recording a match stores a post-event book snapshot.
- Recording a cancel stores the cancel result.
- Snapshots include best bid, best ask, spread, mid price, and depth.
- Snapshots remain unchanged after the live book changes.

### Learning Checkpoint

The user should be able to explain:

- Why the live book and historical snapshots must be separate.
- Why recorder is not owned by exchange yet.
- How depth is represented as immutable price/quantity pairs.

## Phase 6: Deterministic Simulation Loop

### Goal

Create the first event-driven orchestrator.

### Concepts

- Market intent events.
- Finite event sequences.
- Processing one event at a time.
- Coordinating exchange and recorder.
- Simulation result summaries.

### Why This Comes After Recording

The simulator needs a way to process many events and preserve the history of
what happened. `Exchange` can process one action, and `Recorder` can observe one
result. `Simulation` coordinates both over time.

### Design Decision

Simulation events are intent, not official orders.

```text
SubmitLimitOrder:
    Intent before exchange ID/timestamp assignment.

Order:
    Official exchange message after ID/timestamp assignment.
```

This keeps identity and time assignment inside `Exchange`.

### Likely Objects

- `SubmitLimitOrder`
- `SubmitMarketOrder`
- `CancelOrder`
- `Simulation`
- `SimulationResult`

### Testing

Use deterministic unit tests:

- Simulation processes limit and market events.
- Simulation records no-trade resting limit orders.
- Simulation processes cancel events.
- Simulation supports IOC limit events.
- `max_events` stops early.
- `process_event` works incrementally.

### Learning Checkpoint

The user should be able to explain:

- Why simulation is an orchestrator.
- Why simulation events are not `Order` objects.
- How one event flows through simulation, exchange, matching/book, and recorder.

## Phase 7: Basic Agent Interface

### Goal

Let agents observe market state and emit simulation events.

### Concepts

- Agent observation.
- Agent action.
- Scripted events.
- Agent-driven simulation steps.
- Separation between observing and mutating market state.

### Design Decision

Reuse `BookSnapshot` as the first agent observation object.

Reason:

- It already contains top-of-book and depth.
- It is immutable.
- It avoids creating a duplicate `MarketState` object too early.

Agents should emit intent events:

- `SubmitLimitOrder`
- `SubmitMarketOrder`
- `CancelOrder`

Agents should not directly edit `OrderBook`, `MatchingEngine`, or `Exchange`.

### First Agent

`ScriptedAgent` emits a predefined sequence of events.

It records every observation it receives so we can inspect what the agent saw
before each action.

### Testing

Use deterministic unit tests:

- Scripted agent records observations.
- Agent observations include book state created by previous steps.
- Agent loop stops when no events are emitted.
- Agent loop respects `max_steps`.

### Learning Checkpoint

The user should be able to explain:

- What an agent sees.
- Why agents output intent events instead of official `Order` objects.
- How agent actions flow through simulation, exchange, matching/book, and recorder.

### Learning Checkpoint

The user should be able to explain:

- Why bids sort from high to low.
- Why asks sort from low to high.
- Why time priority only applies within the same price level.

## Phase 3: Matching Engine

### Goal

Process incoming orders and generate trades.

### Concepts

- Aggressive order.
- Passive order.
- Crossing the spread.
- Price-time priority.
- Partial fills.
- Full fills.
- Remaining quantity.
- Marketable limit orders.

### Why This Comes Third

Matching is the core market mechanic. Every later feature depends on it.

### Likely Objects

- `MatchingEngine`
- `MatchResult`

### Matching Engine Decision

The matching engine owns execution rules.

It uses `OrderBook` for storage, but it does not expose or manually edit raw
book dictionaries from outside the book API.

Core process:

```text
1. Track incoming_remaining from the immutable Order.quantity.
2. Look at the opposite side of the book.
3. Peek at the best resting BookOrder.
4. Stop if there is no liquidity or the price does not cross.
5. Trade min(incoming_remaining, resting.remaining_quantity).
6. Reduce incoming_remaining.
7. Reduce resting.remaining_quantity.
8. Remove the BookOrder if its remaining quantity reaches zero.
9. Rest or cancel leftover quantity depending on time-in-force.
```

FOK orders require a pre-check:

```text
If the full quantity cannot fill immediately at acceptable prices,
cancel the whole order without mutating the book.
```

### Testing

Use exact scenario tests:

- Buy market order matches the lowest ask first.
- Sell market order matches the highest bid first.
- At the same price, older orders fill first.
- A crossing buy limit order trades at the ask price, not the buyer limit price.
- A crossing sell limit order trades at the bid price, not the seller limit price.
- Partial fill leaves correct remaining quantity.
- Regular limit order rests leftover quantity.
- IOC cancels leftover quantity.
- FOK cancels the entire order if full immediate fill is impossible.

### Learning Checkpoint

The user should be able to walk through a small book and predict all trades from a new incoming order.

## Phase 4: Event-Driven Simulation Loop

### Goal

Create a simulation loop that processes events one by one.

### Concepts

- Market events.
- Simulated clock.
- Event IDs.
- Deterministic event sequence.
- Stop conditions.
- Recording state over time.

### Why This Comes Fourth

After the book and matching engine work, we need a controlled way to feed events into the market.

### Likely Objects

- `MarketEvent`
- `EventSource`
- `Simulation`
- `Recorder`

### Testing

Use deterministic event sequences:

- A sequence of events produces expected final book state.
- A sequence of events produces expected trades.
- `max_events` stops the simulation.
- Recorder captures trades and book snapshots.

### Learning Checkpoint

The user should be able to explain why event-driven simulation is better for order book mechanics than fixed time-step simulation.

## Phase 5: Portfolio And Accounting

### Goal

Track cash, inventory, fees, and PnL.

### Concepts

- Base asset inventory.
- Quote currency cash.
- Realized PnL.
- Mark-to-market PnL.
- Fees.
- Maker vs taker fees.

### Why This Comes Fifth

A market maker cannot be evaluated only by fills. We need accounting to know whether the strategy is making or losing money.

### Testing

Use exact accounting examples:

- Buying increases inventory and decreases cash.
- Selling decreases inventory and increases cash.
- Fees reduce PnL.
- Mark-to-market changes with mid price.

### Learning Checkpoint

The user should be able to explain the difference between earning spread and actually making net PnL after inventory moves and fees.

## Phase 6: First Market Maker

### Goal

Build a simple agent that posts one bid and one ask around a reference price.

### Concepts

- Quoting.
- Spread capture.
- Inventory limits.
- Quote cancellation and replacement.
- Fill risk.

### Why This Comes Sixth

Only after the market mechanics and accounting are working should we add strategy behavior.

### Testing

Use controlled scenarios:

- Market maker places bid and ask.
- Market maker inventory changes after fills.
- Market maker cancels stale quotes.
- Market maker stops quoting when inventory limit is reached.

### Learning Checkpoint

The user should be able to explain when a market maker earns the spread and when that spread is overwhelmed by adverse price movement.

## Phase 7: Order Flow Models

### Goal

Generate synthetic external market activity.

### Concepts

- Noise traders.
- Random limit orders.
- Random market orders.
- Cancellations.
- Order arrival intensity.
- Volatility regimes.

### Why This Comes Seventh

Strategies need a market environment. Synthetic order flow lets us test behavior before using real data.

### Testing

Use seeded randomness:

- Same seed produces same event sequence.
- Generated prices obey tick size.
- Generated quantities are positive.
- Order flow does not create invalid book states.

### Learning Checkpoint

The user should be able to explain what assumptions the synthetic market makes and why those assumptions affect strategy results.

## Phase 8: Realistic Frictions

### Goal

Make the simulator less naive.

### Concepts

- Maker fees and taker fees.
- Tick size.
- Lot size.
- Minimum notional.
- Latency.
- Queue position.
- Cancel/replace delay.
- Slippage.

### Why This Comes Eighth

Naive market making often looks good before frictions. Realism should be added after the base simulator is correct.

### Testing

Use targeted examples:

- Fees change PnL as expected.
- Latency delays agent actions.
- Queue priority affects fills.
- Lot size rejects invalid quantities.

### Learning Checkpoint

The user should be able to explain why frictions can turn a profitable-looking strategy into a losing one.

## Phase 9: Data Replay

### Goal

Replay public crypto exchange data.

### Concepts

- Historical trades.
- Order book snapshots.
- Incremental depth updates.
- Sequence numbers.
- Data cleaning.
- Replay speed.

### Why This Comes Ninth

Real data is useful only after we understand the simulator's internal mechanics. Otherwise, data complexity hides conceptual mistakes.

### Testing

Use small data samples:

- Snapshot plus updates reconstructs expected book state.
- Sequence gaps are detected.
- Replay produces deterministic output.

### Learning Checkpoint

The user should be able to explain the difference between simulating order flow and replaying observed exchange messages.

## Phase 10: Advanced Strategy And Analysis

### Goal

Experiment with more realistic market making models.

### Concepts

- Reservation price.
- Optimal spread.
- Inventory skew.
- Volatility estimation.
- Adverse selection.
- Order book imbalance.
- Queue-reactive models.
- Avellaneda-Stoikov-style quoting.

### Why This Comes Last

Advanced strategy formulas are only useful after the simulator can correctly represent fills, inventory, and market state.

### Testing

Use both deterministic and seeded simulations:

- Strategy respects inventory limits.
- Quotes react to inventory.
- Quotes react to volatility.
- Results include fill rate, PnL, drawdown, inventory distribution, and fee impact.

### Learning Checkpoint

The user should be able to explain what the strategy is optimizing and what assumptions make the model fragile.

## Testing Philosophy

Testing should start with deterministic microstructure scenarios.

The first tests should not depend on randomness.

Good early tests are small stories:

```text
Given:
    Ask: 100.10 | 2 BTC
    Ask: 100.11 | 3 BTC

When:
    Buy limit 4 BTC @ 100.12 arrives

Then:
    Trade 2 BTC @ 100.10
    Trade 2 BTC @ 100.11
    No resting remainder
```

Later, when randomness is introduced:

- Always use seeds.
- Record the seed with the result.
- Separate random generation tests from matching engine correctness tests.

## First Proposed Implementation Target

The first implementation target should be **Phase 1: Orders, Trades, And Basic Concepts**.

Reason:

- It is small.
- It forces us to define vocabulary precisely.
- It creates the objects that later phases will use.
- It lets us test integer quantity and price representation before building book behavior.

The first code should probably include:

- `Side`
- `OrderType`
- `TimeInForce`
- `Order`
- `Trade`

The first tests should verify:

- Market orders do not need prices.
- Limit orders need prices.
- Quantities are positive integers.
- Price ticks are positive integers when provided.
- Filled quantities can be represented exactly.

## Open Questions

These should be discussed before or during implementation:

- What Python package structure should we use?
- Should we use `dataclass` or Pydantic-style validation?
- Should order IDs be generated by the simulator or passed in explicitly?
- Should timestamps be simple integer event numbers at first, or nanosecond-style timestamps?
- Should the first order book support cancellation by order ID immediately, or after basic matching?
- Should we initialize the repository with Git before coding?

## Current Status

Status: planning.

Current agreed ideas:

- The simulator should be event-driven.
- Initial domain is crypto.
- Quantities should be integer sats.
- Prices should be integer ticks internally.
- The first real market mechanic should be a price-time-priority limit order book.
- We should support regular limit orders, IOC, and FOK.

Next decision:

Agree whether Phase 1 is the right first implementation target, then decide the exact Python structure and testing setup.
