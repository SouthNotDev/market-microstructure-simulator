"""Limit order book storage.

The order book is the memory of the exchange. It stores passive/resting limit
orders that are waiting to be executed later.

This module intentionally does not perform matching. The matching engine will
own execution rules such as crossing the spread, partial fills, IOC, and FOK.
Keeping storage separate from matching makes the mechanics easier to test and
understand.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Deque

from market_sim.domain import Order, OrderType, Side


@dataclass(frozen=True)
class BookOrderLocation:
    """Index entry that says where a live BookOrder currently rests.

    The book's primary structure is optimized for matching:

        side -> price -> FIFO queue

    Cancellation has a different access pattern: "find order_id X wherever it
    is." This location object lets the book jump directly to the right side and
    price level before removing the order from that level's FIFO queue.
    """

    side: Side
    price_ticks: int


@dataclass
class BookOrder:
    """Live/open state of an order currently resting in the book.

    `Order` is the original submitted instruction. `BookOrder` is the live
    remainder that the matching engine can reduce as fills happen. Keeping
    these separate preserves history while still letting the book update open
    quantity.
    """

    # Same ID as the original Order. Trades and cancellations can use this ID to
    # connect live book state back to the original instruction.
    order_id: int

    # Side is copied from the original order so the book can keep bid and ask
    # state separate.
    side: Side

    # Resting orders always have a concrete price level.
    price_ticks: int

    # Live quantity still available to trade. This is the field that will shrink
    # after partial fills.
    remaining_quantity: int

    # Original arrival sequence. FIFO priority uses this value when two
    # BookOrders are at the same price level.
    timestamp: int

    @classmethod
    def from_order(cls, order: Order) -> "BookOrder":
        """Create live book state from a validated limit order.

        This is where a historical instruction becomes live resting liquidity.
        The original Order is not mutated; we copy the fields the book needs and
        use `quantity` as the initial `remaining_quantity`.
        """

        if order.order_type != OrderType.LIMIT:
            raise ValueError("Only limit orders can become book orders")

        if order.price_ticks is None:
            raise ValueError("Book orders must have a price")

        return cls(
            order_id=order.order_id,
            side=order.side,
            price_ticks=order.price_ticks,
            remaining_quantity=order.quantity,
            timestamp=order.timestamp,
        )

    def __post_init__(self) -> None:
        if self.order_id <= 0:
            raise ValueError("Book order ID must be positive")

        if self.price_ticks <= 0:
            raise ValueError("Book order price ticks must be positive")

        if self.remaining_quantity <= 0:
            raise ValueError("Book order remaining quantity must be positive")

        if self.timestamp <= 0:
            raise ValueError("Book order timestamp must be positive")


@dataclass
class PriceLevel:
    """FIFO queue of resting orders at one price.

    A price level groups all resting orders with the same side and same price.
    If two orders have the same price, time priority decides who fills first.
    A deque models that queue naturally: append new orders at the back, consume
    older orders from the front later in the matching engine.
    """

    # The shared price for every order in this queue, represented in integer
    # ticks so price comparisons are exact.
    price_ticks: int

    # Live resting orders in arrival order. The left/front of the deque is the
    # oldest order and therefore has priority at this price.
    orders: Deque[BookOrder] = field(default_factory=deque)

    def __post_init__(self) -> None:
        # A price level at zero or a negative price has no economic meaning and
        # would break best-bid/best-ask calculations.
        if self.price_ticks <= 0:
            raise ValueError("Price level ticks must be positive")

    @property
    def total_quantity(self) -> int:
        """Total visible liquidity resting at this price level."""

        # We calculate this directly from orders so the level cannot drift out
        # of sync with its queue. Later, if performance matters, we can cache it.
        return sum(order.remaining_quantity for order in self.orders)

    def add_order(self, order: BookOrder) -> None:
        """Append a live resting order behind older orders at the same price."""

        # This protects the price-level invariant: one PriceLevel represents one
        # price only. Without this check, FIFO priority at that price would be
        # mixed with orders that belong somewhere else.
        if order.price_ticks != self.price_ticks:
            raise ValueError("Order price must match price level")

        # New orders go to the back of the queue because older orders at the
        # same price must fill first.
        self.orders.append(order)

    def as_tuple(self) -> tuple[BookOrder, ...]:
        """Return an immutable view of the queue for tests and inspection."""

        # Returning a tuple prevents callers from accidentally mutating the
        # internal deque. Matching will later use dedicated methods to consume
        # orders instead of external code editing storage directly.
        return tuple(self.orders)


@dataclass
class OrderBook:
    """Stores resting buy and sell limit orders.

    The book is organized as:

        side -> price_ticks -> PriceLevel -> FIFO queue of orders

    Bids and asks are stored separately because they have opposite price
    priority:

    - Bids: highest price is best.
    - Asks: lowest price is best.
    """

    # Mapping from bid price to the FIFO queue at that price.
    bids: dict[int, PriceLevel] = field(default_factory=dict)

    # Mapping from ask price to the FIFO queue at that price.
    asks: dict[int, PriceLevel] = field(default_factory=dict)

    # Secondary index for cancellation. The key is order_id, and the value tells
    # us which side and price level contains the live BookOrder.
    orders_by_id: dict[int, BookOrderLocation] = field(default_factory=dict)

    def add_resting_order(self, order: Order) -> None:
        """Add a passive limit order to the book.

        The matching engine is responsible for deciding whether an incoming
        order should rest. This method assumes that decision has already been
        made and only stores valid resting limit orders.
        """

        # Only limit orders can become passive liquidity. A market order has no
        # price and therefore cannot be stored at a price level.
        if order.order_type != OrderType.LIMIT:
            raise ValueError("Only limit orders can rest in the book")

        # The Order dataclass already enforces this for limit orders. We keep
        # the check here too because this method is the storage boundary: every
        # resting order must belong to a concrete price level.
        if order.price_ticks is None:
            raise ValueError("Resting orders must have a price")

        if order.order_id in self.orders_by_id:
            raise ValueError("Order ID is already resting in the book")

        # Choose bid or ask storage based on order side. Then either retrieve
        # the existing level at that price or create a new one.
        levels = self._levels_for_side(order.side)
        level = levels.setdefault(order.price_ticks, PriceLevel(order.price_ticks))

        # The level itself handles FIFO insertion.
        # Convert the immutable submitted instruction into mutable live state.
        # From this point on, the book tracks remaining_quantity through the
        # BookOrder while the original Order stays unchanged for history.
        book_order = BookOrder.from_order(order)
        level.add_order(book_order)

        # Keep the cancellation index synchronized with primary storage.
        self.orders_by_id[book_order.order_id] = BookOrderLocation(
            side=book_order.side,
            price_ticks=book_order.price_ticks,
        )

    @property
    def best_bid(self) -> int | None:
        """Highest resting buy price, or None if there are no bids."""

        if not self.bids:
            return None

        # Buyers compete by paying more, so the best bid is the maximum bid
        # price currently resting in the book.
        return max(self.bids)

    @property
    def best_ask(self) -> int | None:
        """Lowest resting sell price, or None if there are no asks."""

        if not self.asks:
            return None

        # Sellers compete by accepting less, so the best ask is the minimum ask
        # price currently resting in the book.
        return min(self.asks)

    @property
    def spread(self) -> int | None:
        """Distance between best ask and best bid, measured in ticks."""

        # If one side is empty, there is no two-sided market yet, so spread is
        # undefined.
        if self.best_bid is None or self.best_ask is None:
            return None

        return self.best_ask - self.best_bid

    @property
    def mid_price(self) -> Decimal | None:
        """Average of best bid and best ask.

        Decimal is used so half-tick mids such as 10005.5 are exact and clear.
        The matching engine will still use integer ticks for execution prices.
        """

        if self.best_bid is None or self.best_ask is None:
            return None

        return (Decimal(self.best_bid) + Decimal(self.best_ask)) / Decimal(2)

    def depth_at(self, side: Side, price_ticks: int) -> int:
        """Total resting quantity at one side and price."""

        # This method is useful for inspecting book liquidity without exposing
        # the internal dictionaries.
        if price_ticks <= 0:
            raise ValueError("Price ticks must be positive")

        level = self._levels_for_side(side).get(price_ticks)
        if level is None:
            return 0

        return level.total_quantity

    def orders_at(self, side: Side, price_ticks: int) -> tuple[BookOrder, ...]:
        """Orders resting at one side and price, in FIFO order."""

        # This lets tests and learning examples verify time priority directly:
        # the first order in the tuple is the first one that should fill later.
        if price_ticks <= 0:
            raise ValueError("Price ticks must be positive")

        level = self._levels_for_side(side).get(price_ticks)
        if level is None:
            return ()

        return level.as_tuple()

    def best_price_for_side(self, side: Side) -> int | None:
        """Best resting price for one side.

        This gives the future matching engine a side-neutral way to ask:
        "What is the best available price on the side I want to trade against?"
        """

        if side == Side.BUY:
            return self.best_bid

        return self.best_ask

    def best_level_for_side(self, side: Side) -> PriceLevel | None:
        """PriceLevel with highest priority for one side, if it exists."""

        best_price = self.best_price_for_side(side)
        if best_price is None:
            return None

        return self._levels_for_side(side)[best_price]

    def peek_best_order(self, side: Side) -> BookOrder | None:
        """First order that would be matched on this side.

        "Peek" means inspect without removing. The matching engine will use this
        to decide whether a trade can happen and how much quantity is available.
        """

        level = self.best_level_for_side(side)
        if level is None or not level.orders:
            return None

        # The left/front of the deque is oldest order at the best price, so it
        # has both price priority and time priority.
        return level.orders[0]

    def remove_best_order(self, side: Side) -> BookOrder | None:
        """Remove and return the first order at the best price level.

        The matching engine should call this after the best BookOrder reaches
        zero remaining quantity. If removing it empties the price level, the
        level is removed too, so the book does not keep dead liquidity.
        """

        best_price = self.best_price_for_side(side)
        if best_price is None:
            return None

        levels = self._levels_for_side(side)
        level = levels[best_price]
        if not level.orders:
            del levels[best_price]
            return None

        removed_order = level.orders.popleft()
        self.orders_by_id.pop(removed_order.order_id, None)

        # Empty price levels should disappear. Otherwise best bid/ask and depth
        # would see a price with no live quantity behind it.
        if not level.orders:
            del levels[best_price]

        return removed_order

    def cancel_order(self, order_id: int) -> BookOrder | None:
        """Fully remove one live resting order by ID.

        Cancellation is not matching: it does not create a trade. It simply
        removes the remaining live quantity from the book. If the order ID is
        not currently resting, the method returns None.
        """

        if order_id <= 0:
            raise ValueError("Order ID must be positive")

        location = self.orders_by_id.pop(order_id, None)
        if location is None:
            return None

        levels = self._levels_for_side(location.side)
        level = levels[location.price_ticks]

        # A deque is efficient at removing from the front, but cancellation can
        # target any order in the queue. For this first simulator version we do
        # a clear linear scan inside the one known price level.
        for index, book_order in enumerate(level.orders):
            if book_order.order_id == order_id:
                del level.orders[index]

                if not level.orders:
                    del levels[location.price_ticks]

                return book_order

        # If this ever happens, the index and primary storage disagree. That is
        # a book integrity bug, so fail loudly instead of hiding it.
        raise RuntimeError("Order index pointed to a missing book order")

    def price_levels(self, side: Side) -> tuple[int, ...]:
        """Visible price levels sorted in matching priority order."""

        levels = self._levels_for_side(side)

        # Buy side sorts descending because higher bids are better for sellers
        # who want to hit the bid. Sell side sorts ascending because lower asks
        # are better for buyers who want to lift the ask.
        reverse = side == Side.BUY
        return tuple(sorted(levels, reverse=reverse))

    def _levels_for_side(self, side: Side) -> dict[int, PriceLevel]:
        """Return the internal price-level map for one side."""

        if side == Side.BUY:
            return self.bids

        return self.asks
