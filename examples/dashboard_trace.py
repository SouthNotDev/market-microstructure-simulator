"""Generate dashboard trace data from the current simulator.

The dashboard is visual, but the states should come from the simulator we have
built. This script runs a small deterministic sequence through `Simulation` and
exports a compact JSON trace that the static dashboard can animate.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from market_sim import Side, Simulation, SubmitLimitOrder, SubmitMarketOrder


AGENTS = [f"Agent {index:02d}" for index in range(1, 25)]


def display_price(price_ticks: int | Decimal | None) -> str:
    if price_ticks is None:
        return "-"

    return f"{Decimal(price_ticks) / Decimal(100):.3f}".rstrip("0").rstrip(".")


def compact_depth(depth: tuple[tuple[int, int], ...], book=None, side: Side | None = None) -> list[dict[str, str | int]]:
    return [
        {
            "price": display_price(price),
            "priceTicks": price,
            "size": quantity,
            "orders": len(book.orders_at(side, price)) if book is not None and side is not None else 1,
        }
        for price, quantity in depth
    ]


def snapshot_payload(snapshot, book=None) -> dict[str, object]:
    return {
        "bestBid": display_price(snapshot.best_bid),
        "bestAsk": display_price(snapshot.best_ask),
        "spread": snapshot.spread,
        "midPrice": display_price(snapshot.mid_price),
        "midRaw": float(snapshot.mid_price) / 100 if snapshot.mid_price is not None else None,
        "bidDepth": compact_depth(snapshot.bid_depth, book, Side.BUY),
        "askDepth": compact_depth(snapshot.ask_depth, book, Side.SELL),
    }


def event_payload(event, event_index: int, agent: str) -> dict[str, object]:
    if isinstance(event, SubmitLimitOrder):
        return {
            "kind": "LIMIT",
            "side": event.side.value.upper(),
            "quantity": event.quantity,
            "price": display_price(event.price_ticks),
            "priceTicks": event.price_ticks,
            "label": f"{event.side.value.upper()} {event.quantity} @ {display_price(event.price_ticks)}",
            "agent": agent,
        }

    if isinstance(event, SubmitMarketOrder):
        return {
            "kind": "MARKET",
            "side": event.side.value.upper(),
            "quantity": event.quantity,
            "price": "MKT",
            "priceTicks": None,
            "label": f"{event.side.value.upper()} {event.quantity} MARKET",
            "agent": agent,
        }

    raise TypeError(f"Unsupported event: {event!r}")


def seed_events(rng: random.Random) -> list[tuple[str, SubmitLimitOrder | SubmitMarketOrder]]:
    """Create a two-sided book whose top levels can move during the demo."""

    events: list[tuple[str, SubmitLimitOrder | SubmitMarketOrder]] = []

    for offset in range(12):
        bid_price = 10_000 - offset
        ask_price = 10_001 + offset
        order_count = 1 if offset < 3 else rng.choice([1, 2, 2, 3])
        quantity_choices = [20, 30, 45, 60, 80] if offset < 3 else [75, 100, 125, 150, 200, 250]

        for _ in range(order_count):
            events.append(
                (
                    rng.choice(AGENTS),
                    SubmitLimitOrder(Side.BUY, quantity=rng.choice(quantity_choices), price_ticks=bid_price),
                )
            )

        for _ in range(order_count):
            events.append(
                (
                    rng.choice(AGENTS),
                    SubmitLimitOrder(Side.SELL, quantity=rng.choice(quantity_choices), price_ticks=ask_price),
                )
            )

    rng.shuffle(events)
    return events


def adaptive_event(rng: random.Random, simulation: Simulation) -> tuple[str, SubmitLimitOrder | SubmitMarketOrder]:
    """Emit order flow around the live book, using current top-of-book state."""

    observation = simulation.current_observation()
    best_bid = observation.best_bid or 10_000
    best_ask = observation.best_ask or 10_001
    agent = rng.choice(AGENTS)

    if observation.best_bid is not None and observation.best_ask is not None and rng.random() < 0.58:
        side = rng.choice([Side.BUY, Side.SELL])
        contra_depth = observation.ask_depth if side == Side.BUY else observation.bid_depth
        top_quantity = contra_depth[0][1]
        nearby_quantity = sum(quantity for _, quantity in contra_depth[:3])

        if len(contra_depth) >= 2 and nearby_quantity > top_quantity + 1:
            quantity = min(nearby_quantity - 1, top_quantity + rng.choice([5, 15, 25, 40, 60, 90]))
        else:
            quantity = rng.choice([max(1, top_quantity // 2), top_quantity])

        return agent, SubmitMarketOrder(side, quantity=quantity)

    side = rng.choice([Side.BUY, Side.SELL])
    mode = rng.random()
    quantity = rng.choice([25, 35, 50, 75, 100, 140, 180, 240, 320, 420])

    if side == Side.BUY:
        if mode < 0.20:
            price_ticks = best_ask
        elif mode < 0.52 and best_ask - best_bid > 1:
            price_ticks = rng.randint(best_bid + 1, best_ask - 1)
        else:
            price_ticks = best_bid - rng.choice([0, 0, 1, 1, 2, 3, 4])
    else:
        if mode < 0.20:
            price_ticks = best_bid
        elif mode < 0.52 and best_ask - best_bid > 1:
            price_ticks = rng.randint(best_bid + 1, best_ask - 1)
        else:
            price_ticks = best_ask + rng.choice([0, 0, 1, 1, 2, 3, 4])

    return agent, SubmitLimitOrder(side, quantity=quantity, price_ticks=max(1, price_ticks))


def main() -> None:
    rng = random.Random(25_000)
    simulation = Simulation()
    events = seed_events(rng)
    target_events = 260

    steps = []
    mid_series: list[dict[str, float | int]] = []

    for index in range(1, target_events + 1):
        if index <= len(events):
            agent, event = events[index - 1]
        else:
            agent, event = adaptive_event(rng, simulation)

        before = simulation.current_observation()
        result = simulation.process_event(event)
        after = simulation.recorder.snapshots[-1]

        if after.mid_price is not None:
            mid_series.append({"x": index, "y": float(after.mid_price) / 100})

        trades = [
            {
                "tradeId": trade.trade_id,
                "price": display_price(trade.price_ticks),
                "quantity": trade.quantity,
                "aggressor": trade.aggressor_side.value.upper(),
                "restingOrderId": trade.resting_order_id,
            }
            for trade in result.trades
        ]

        status = "RESTING"
        if result.filled_quantity and result.resting_quantity:
            status = "PARTIAL + REST"
        elif result.filled_quantity and result.canceled_quantity:
            status = "PARTIAL + CANCEL"
        elif result.filled_quantity:
            status = "MATCHED"
        elif result.canceled_quantity:
            status = "CANCELED"

        steps.append(
            {
                "eventNumber": index,
                "event": event_payload(event, index, agent),
                "incomingOrderId": result.incoming_order_id,
                "timestamp": result.timestamp,
                "status": status,
                "filledQuantity": result.filled_quantity,
                "canceledQuantity": result.canceled_quantity,
                "restingQuantity": result.resting_quantity,
                "trades": trades,
                "before": snapshot_payload(before, simulation.exchange.book),
                "after": snapshot_payload(after, simulation.exchange.book),
                "midSeries": list(mid_series),
            }
        )

    default_step_index = 0
    best_score = -1
    for index, step in enumerate(steps):
        if step["after"]["midRaw"] is None:
            continue

        recent_mids = [point["y"] for point in step["midSeries"][-22:]]
        mid_changes = sum(1 for left, right in zip(recent_mids, recent_mids[1:]) if left != right)
        score = mid_changes + (2 if step["filledQuantity"] > 0 else 0)
        if score > best_score:
            best_score = score
            default_step_index = index

    output = {
        "symbol": "ABC",
        "title": "Market Microstructure Simulator",
        "agents": AGENTS,
        "defaultStepIndex": default_step_index,
        "steps": steps,
    }

    target = ROOT / "dashboard" / "trace.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
