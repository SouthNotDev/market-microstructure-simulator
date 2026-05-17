"""Recording helpers for market history and book state.

The recorder is intentionally separate from Exchange. Exchange changes market
state; Recorder observes results and saves history for later analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from market_sim.book import OrderBook
from market_sim.domain import CancelResult, MatchResult, Side, Trade


@dataclass(frozen=True)
class BookSnapshot:
    """Immutable view of the order book after an event.

    A snapshot freezes top-of-book and depth information at one timestamp. This
    matters because the live OrderBook keeps changing; analysis needs historical
    states that do not mutate after being recorded.
    """

    timestamp: int
    best_bid: int | None
    best_ask: int | None
    spread: int | None
    mid_price: Decimal | None
    bid_depth: tuple[tuple[int, int], ...]
    ask_depth: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if self.timestamp <= 0:
            raise ValueError("Snapshot timestamp must be positive")

        for price_ticks, quantity in self.bid_depth + self.ask_depth:
            if price_ticks <= 0:
                raise ValueError("Snapshot price ticks must be positive")

            if quantity < 0:
                raise ValueError("Snapshot quantity cannot be negative")


@dataclass
class Recorder:
    """Collects market history without affecting market behavior."""

    match_results: list[MatchResult] = field(default_factory=list)
    cancel_results: list[CancelResult] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    snapshots: list[BookSnapshot] = field(default_factory=list)

    def record_match(self, result: MatchResult, book: OrderBook) -> BookSnapshot:
        """Store one match result, its trades, and a post-event book snapshot."""

        self.match_results.append(result)
        self.trades.extend(result.trades)

        timestamp = self._timestamp_for_match(result)
        snapshot = self.snapshot(book, timestamp)
        self.snapshots.append(snapshot)
        return snapshot

    def record_cancel(self, result: CancelResult, book: OrderBook) -> BookSnapshot:
        """Store one cancel result and a post-event book snapshot."""

        self.cancel_results.append(result)

        snapshot = self.snapshot(book, result.timestamp)
        self.snapshots.append(snapshot)
        return snapshot

    def snapshot(self, book: OrderBook, timestamp: int) -> BookSnapshot:
        """Create an immutable depth snapshot from the current live book."""

        return BookSnapshot(
            timestamp=timestamp,
            best_bid=book.best_bid,
            best_ask=book.best_ask,
            spread=book.spread,
            mid_price=book.mid_price,
            bid_depth=self._depth_for_side(book, Side.BUY),
            ask_depth=self._depth_for_side(book, Side.SELL),
        )

    def _depth_for_side(self, book: OrderBook, side: Side) -> tuple[tuple[int, int], ...]:
        """Convert live price levels into immutable `(price, quantity)` pairs."""

        return tuple(
            (price_ticks, book.depth_at(side, price_ticks))
            for price_ticks in book.price_levels(side)
        )

    def _timestamp_for_match(self, result: MatchResult) -> int:
        """Use the incoming order event timestamp for a match result.

        MatchResult stores the incoming order timestamp directly so no-trade
        resting orders can still be recorded.
        """

        return result.timestamp
