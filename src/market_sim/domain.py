"""Core domain objects for the market simulator.

This module is the vocabulary layer of the simulator. It defines the market
objects that every later component will pass around: orders, trades, and match
results.

The important design choice here is that these objects validate themselves as
soon as they are created. That means the future matching engine can focus on
market mechanics instead of repeatedly checking for impossible inputs.

This module does not perform matching. It only makes sure the data entering
the rest of the system is coherent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Side(Enum):
    """Economic side of an order or aggressor.

    We use an enum instead of raw strings so the code has only two valid
    choices: buy or sell. This prevents bugs from typos such as "Buy", "bid",
    or "long" leaking into the matching logic.
    """

    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """How an order asks the exchange to execute.

    LIMIT and MARKET are different execution instructions:

    - LIMIT: trade only at the order's price or better.
    - MARKET: trade immediately against available liquidity.

    The matching engine will later use this field to decide whether the order
    has price protection.
    """

    LIMIT = "limit"
    MARKET = "market"


class TimeInForce(Enum):
    """Instruction for what happens to quantity that cannot fill immediately.

    Time-in-force is separate from order type on purpose. For example, a limit
    order can be regular/GTC, IOC, or FOK. Those are all limit orders, but they
    handle unfilled quantity differently.
    """

    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


@dataclass(frozen=True)
class Order:
    """A validated instruction sent to the matching engine.

    Quantity is an integer number of base units. For BTC examples, that means
    satoshis. Prices are integer ticks, not floating point quote-currency
    values.
    """

    # Unique identifier for this order. Later, cancellations and trades will
    # refer back to orders by this ID.
    order_id: int

    # BUY orders demand the base asset. SELL orders supply the base asset.
    side: Side

    # LIMIT or MARKET. This controls whether price_ticks is required.
    order_type: OrderType

    # Integer base units. For BTC examples this means satoshis, not float BTC.
    quantity: int

    # Simple event sequence for now: 1, 2, 3, ...
    # This gives us time priority without needing real exchange timestamps yet.
    timestamp: int

    # Integer price ticks. None is only valid for market orders because market
    # orders ask the book to find the best available execution prices.
    price_ticks: int | None = None

    # Defaults to GTC because a plain limit order usually rests until it trades
    # or is canceled. Market orders override this because they cannot rest.
    time_in_force: TimeInForce = TimeInForce.GTC

    def __post_init__(self) -> None:
        """Reject impossible order instructions at creation time.

        This is the "validate early" boundary. If an invalid order is allowed
        into the matching engine, every later function would need defensive
        checks. By rejecting bad orders here, the rest of the simulator can
        assume it is working with coherent market instructions.
        """

        # IDs are positive so missing/placeholder IDs like 0 cannot be confused
        # with real orders in trades, cancellations, or match results.
        if self.order_id <= 0:
            raise ValueError("Order ID must be positive")

        # Zero or negative size has no market meaning. A trade for 0 sats should
        # never appear in the book or matching results.
        if self.quantity <= 0:
            raise ValueError("Order quantity must be positive")

        # We use positive integer timestamps as event sequence numbers. This is
        # enough for FIFO queue priority inside one price level.
        if self.timestamp <= 0:
            raise ValueError("Order timestamp must be positive")

        # A limit order means "trade at this price or better", so it cannot be
        # interpreted without a limit price.
        if self.order_type == OrderType.LIMIT and self.price_ticks is None:
            raise ValueError("Limit orders must have a price")

        # A market order means "trade now against the book"; adding a limit
        # price would make it a marketable limit order, not a pure market order.
        if self.order_type == OrderType.MARKET and self.price_ticks is not None:
            raise ValueError("Market orders should not have a limit price")

        # Prices are integer ticks, but they still must be economically valid.
        # A zero or negative price would break price priority and PnL accounting.
        if self.price_ticks is not None and self.price_ticks <= 0:
            raise ValueError("Price ticks must be positive")

        # GTC means leftover quantity can rest in the book. A pure market order
        # has no limit price, so leftover quantity cannot become resting
        # liquidity at any price.
        if self.order_type == OrderType.MARKET and self.time_in_force == TimeInForce.GTC:
            raise ValueError("Market orders cannot rest, so they cannot use GTC")


@dataclass(frozen=True)
class Trade:
    """A completed exchange between one aggressive order and one resting order.

    A trade is more than just price and quantity. We also record which order
    bought, which order sold, which order was aggressive, and which order was
    resting. That context lets us later analyze buyer-initiated flow,
    seller-initiated flow, market-maker passive fills, and adverse selection.
    """

    # Unique execution ID. One incoming order can create multiple trades if it
    # walks through several resting orders or price levels.
    trade_id: int

    # Execution price in integer ticks. The matching engine will later choose
    # the resting order's price, not necessarily the incoming order's limit.
    price_ticks: int

    # Filled quantity in integer base units, such as sats.
    quantity: int

    # Economic roles: who bought and who sold the base asset.
    buyer_order_id: int
    seller_order_id: int

    # Microstructure roles: who took liquidity and who provided liquidity.
    aggressor_order_id: int
    resting_order_id: int

    # Whether the aggressive order was buying or selling. This lets us classify
    # trades as buyer-initiated or seller-initiated without reconstructing the
    # old book state.
    aggressor_side: Side

    # Event sequence number when the trade happened.
    timestamp: int

    def __post_init__(self) -> None:
        """Reject internally inconsistent trade records.

        The matching engine will create Trade objects later. These checks make
        sure every trade tells a coherent story: exactly one buyer, one seller,
        one aggressor, and one resting order.
        """

        if self.trade_id <= 0:
            raise ValueError("Trade ID must be positive")

        # Executions cannot happen at zero/negative prices or sizes.
        if self.price_ticks <= 0:
            raise ValueError("Trade price ticks must be positive")

        if self.quantity <= 0:
            raise ValueError("Trade quantity must be positive")

        if self.buyer_order_id <= 0:
            raise ValueError("Buyer order ID must be positive")

        if self.seller_order_id <= 0:
            raise ValueError("Seller order ID must be positive")

        if self.aggressor_order_id <= 0:
            raise ValueError("Aggressor order ID must be positive")

        if self.resting_order_id <= 0:
            raise ValueError("Resting order ID must be positive")

        if self.timestamp <= 0:
            raise ValueError("Trade timestamp must be positive")

        # A single order cannot trade with itself. In a real exchange, self-trade
        # prevention is more nuanced, but for our simulator this invariant keeps
        # trades simple and coherent.
        if self.buyer_order_id == self.seller_order_id:
            raise ValueError("Buyer and seller orders must be different")

        # The aggressor and resting order must be the two orders involved in the
        # trade. They cannot refer to unrelated order IDs.
        expected_ids = {self.buyer_order_id, self.seller_order_id}
        if self.aggressor_order_id not in expected_ids:
            raise ValueError("Aggressor order must be either the buyer or seller order")

        if self.resting_order_id not in expected_ids:
            raise ValueError("Resting order must be either the buyer or seller order")

        if self.aggressor_order_id == self.resting_order_id:
            raise ValueError("Aggressor and resting orders must be different")

        # If the aggressive side is BUY, the aggressor must be the buyer. This
        # catches contradictory records such as "buy aggressor" but seller ID
        # marked as the aggressor.
        if self.aggressor_side == Side.BUY and self.aggressor_order_id != self.buyer_order_id:
            raise ValueError("Buy aggressor must be the buyer order")

        # Same idea for seller-initiated trades.
        if self.aggressor_side == Side.SELL and self.aggressor_order_id != self.seller_order_id:
            raise ValueError("Sell aggressor must be the seller order")


@dataclass(frozen=True)
class MatchResult:
    """Structured result returned after processing one incoming order.

    The matching engine should not silently mutate the book and leave the rest
    of the simulator guessing. A MatchResult is the receipt for one incoming
    order: what traded, what was canceled, and what remains resting.
    """

    # The order that caused this matching attempt.
    incoming_order_id: int

    # Event sequence number for the incoming order that produced this result.
    timestamp: int

    # All executions generated by this incoming order. Tuple keeps the result
    # immutable from the outside, which protects historical records.
    trades: tuple[Trade, ...] = field(default_factory=tuple)

    # Total quantity that traded. We store it explicitly for convenience, but
    # validate it against trades so the summary cannot drift from the details.
    filled_quantity: int = 0

    # Quantity canceled by IOC/FOK behavior or other future rules.
    canceled_quantity: int = 0

    # Quantity that became passive liquidity after matching, only possible for
    # regular limit orders.
    resting_quantity: int = 0

    # If quantity rests, this tells later components which book order represents
    # that resting remainder.
    resting_order_id: int | None = None

    def __post_init__(self) -> None:
        """Validate the matching receipt.

        These checks protect downstream accounting and recording. For example,
        portfolio code should be able to trust that filled_quantity equals the
        actual sum of trade quantities.
        """

        if self.incoming_order_id <= 0:
            raise ValueError("Incoming order ID must be positive")

        if self.timestamp <= 0:
            raise ValueError("Match result timestamp must be positive")

        if self.filled_quantity < 0:
            raise ValueError("Filled quantity cannot be negative")

        if self.canceled_quantity < 0:
            raise ValueError("Canceled quantity cannot be negative")

        if self.resting_quantity < 0:
            raise ValueError("Resting quantity cannot be negative")

        # Resting quantity and resting order ID must appear together. Having one
        # without the other would leave the simulator unable to trace the
        # leftover order in the book.
        if self.resting_quantity > 0 and self.resting_order_id is None:
            raise ValueError("Resting quantity requires a resting order ID")

        if self.resting_quantity == 0 and self.resting_order_id is not None:
            raise ValueError("Resting order ID requires positive resting quantity")

        if self.resting_order_id is not None and self.resting_order_id <= 0:
            raise ValueError("Resting order ID must be positive")

        # This keeps the detailed trade list and summary fields synchronized.
        trade_quantity = sum(trade.quantity for trade in self.trades)
        if self.filled_quantity != trade_quantity:
            raise ValueError("Filled quantity must equal total trade quantity")


@dataclass(frozen=True)
class CancelResult:
    """Structured receipt for one cancellation request.

    The order book can remove and return a live BookOrder, but the higher-level
    exchange boundary should return an event-style result. That result records
    whether the cancel was accepted, how much live quantity was removed, and the
    timestamp of the cancellation attempt.
    """

    # The order ID the caller attempted to cancel.
    order_id: int

    # True if the order was live and got removed from the book.
    accepted: bool

    # Quantity removed from live book liquidity. This is zero for rejected or
    # not-found cancels.
    canceled_quantity: int

    # Event sequence number assigned by the exchange gateway.
    timestamp: int

    def __post_init__(self) -> None:
        if self.order_id <= 0:
            raise ValueError("Cancel result order ID must be positive")

        if self.canceled_quantity < 0:
            raise ValueError("Canceled quantity cannot be negative")

        if self.timestamp <= 0:
            raise ValueError("Cancel timestamp must be positive")

        if not self.accepted and self.canceled_quantity != 0:
            raise ValueError("Rejected cancels cannot have canceled quantity")

        if self.accepted and self.canceled_quantity <= 0:
            raise ValueError("Accepted cancels must remove positive quantity")
