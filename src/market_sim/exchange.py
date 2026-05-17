"""Exchange gateway for assigning IDs and timestamps.

The exchange gateway is the boundary between high-level intent and validated
market messages. Agents should eventually call this layer instead of manually
creating Order objects with their own IDs and timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from market_sim.book import OrderBook
from market_sim.domain import CancelResult, MatchResult, Order, OrderType, Side, TimeInForce
from market_sim.matching import MatchingEngine


@dataclass
class Exchange:
    """Small exchange-like interface around the book and matching engine.

    This class owns monotonically increasing order IDs and timestamps. That
    keeps identity generation in one place and leaves the lower-level objects
    focused on their own jobs:

    - Order stores an already assigned ID and timestamp.
    - MatchingEngine executes orders.
    - OrderBook stores and cancels live liquidity.
    """

    book: OrderBook = field(default_factory=OrderBook)
    next_order_id: int = 1
    next_timestamp: int = 1
    engine: MatchingEngine = field(init=False)

    def __post_init__(self) -> None:
        if self.next_order_id <= 0:
            raise ValueError("Next order ID must be positive")

        if self.next_timestamp <= 0:
            raise ValueError("Next timestamp must be positive")

        # The engine and the exchange share the same book. Submissions go
        # through the engine; cancellations go directly to book.cancel_order.
        self.engine = MatchingEngine(self.book)

    def submit_limit_order(
        self,
        side: Side,
        quantity: int,
        price_ticks: int,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> MatchResult:
        """Assign ID/timestamp, create a limit Order, and process it."""

        order = Order(
            order_id=self._take_order_id(),
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            timestamp=self._take_timestamp(),
            price_ticks=price_ticks,
            time_in_force=time_in_force,
        )
        return self.engine.process_order(order)

    def submit_market_order(self, side: Side, quantity: int) -> MatchResult:
        """Assign ID/timestamp, create a market Order, and process it."""

        order = Order(
            order_id=self._take_order_id(),
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            timestamp=self._take_timestamp(),
            time_in_force=TimeInForce.IOC,
        )
        return self.engine.process_order(order)

    def cancel_order(self, order_id: int) -> CancelResult:
        """Cancel all remaining live quantity for an order ID."""

        timestamp = self._take_timestamp()
        canceled_order = self.book.cancel_order(order_id)
        if canceled_order is None:
            return CancelResult(
                order_id=order_id,
                accepted=False,
                canceled_quantity=0,
                timestamp=timestamp,
            )

        return CancelResult(
            order_id=order_id,
            accepted=True,
            canceled_quantity=canceled_order.remaining_quantity,
            timestamp=timestamp,
        )

    def _take_order_id(self) -> int:
        """Return the next order ID and advance the counter."""

        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    def _take_timestamp(self) -> int:
        """Return the next event timestamp and advance the counter."""

        timestamp = self.next_timestamp
        self.next_timestamp += 1
        return timestamp
