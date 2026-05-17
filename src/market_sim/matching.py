"""Matching engine for processing incoming orders.

The matching engine owns execution rules. It uses the OrderBook as storage, but
it decides whether an incoming order crosses, how much fills, which trades are
created, and what happens to leftover quantity.
"""

from __future__ import annotations

from dataclasses import dataclass

from market_sim.book import BookOrder, OrderBook
from market_sim.domain import MatchResult, Order, OrderType, Side, TimeInForce, Trade


@dataclass
class MatchingEngine:
    """Applies exchange matching rules to one incoming order at a time."""

    book: OrderBook
    next_trade_id: int = 1

    def process_order(self, order: Order) -> MatchResult:
        """Process one validated incoming order and return a matching receipt.

        The incoming `Order` is immutable historical input, so this method never
        edits `order.quantity`. Instead, it tracks a local `incoming_remaining`
        value while matching. Resting `BookOrder` objects are live book state, so
        their `remaining_quantity` is reduced as trades happen.
        """

        if order.time_in_force == TimeInForce.FOK and not self._has_enough_liquidity_for_fok(order):
            return MatchResult(
                incoming_order_id=order.order_id,
                timestamp=order.timestamp,
                trades=(),
                filled_quantity=0,
                canceled_quantity=order.quantity,
            )

        trades, incoming_remaining = self._match(order)
        filled_quantity = sum(trade.quantity for trade in trades)

        resting_quantity = 0
        resting_order_id = None
        canceled_quantity = 0

        if incoming_remaining > 0:
            if self._should_rest_leftover(order):
                leftover_order = Order(
                    order_id=order.order_id,
                    side=order.side,
                    order_type=OrderType.LIMIT,
                    quantity=incoming_remaining,
                    timestamp=order.timestamp,
                    price_ticks=order.price_ticks,
                    time_in_force=TimeInForce.GTC,
                )
                self.book.add_resting_order(leftover_order)
                resting_quantity = incoming_remaining
                resting_order_id = order.order_id
            else:
                canceled_quantity = incoming_remaining

        return MatchResult(
            incoming_order_id=order.order_id,
            timestamp=order.timestamp,
            trades=tuple(trades),
            filled_quantity=filled_quantity,
            canceled_quantity=canceled_quantity,
            resting_quantity=resting_quantity,
            resting_order_id=resting_order_id,
        )

    def _match(self, order: Order) -> tuple[list[Trade], int]:
        """Consume opposite-side liquidity while the order can trade."""

        incoming_remaining = order.quantity
        trades: list[Trade] = []
        opposite_side = self._opposite_side(order.side)

        while incoming_remaining > 0:
            resting_order = self.book.peek_best_order(opposite_side)
            if resting_order is None:
                break

            if not self._can_cross(order, resting_order.price_ticks):
                break

            trade_quantity = min(incoming_remaining, resting_order.remaining_quantity)
            trades.append(self._create_trade(order, resting_order, trade_quantity))

            incoming_remaining -= trade_quantity
            resting_order.remaining_quantity -= trade_quantity

            if resting_order.remaining_quantity == 0:
                self.book.remove_best_order(opposite_side)

        return trades, incoming_remaining

    def _can_cross(self, order: Order, resting_price_ticks: int) -> bool:
        """Return whether the incoming order can trade at a resting price."""

        if order.order_type == OrderType.MARKET:
            return True

        if order.price_ticks is None:
            raise ValueError("Limit order needs a price to determine crossing")

        if order.side == Side.BUY:
            return order.price_ticks >= resting_price_ticks

        return order.price_ticks <= resting_price_ticks

    def _has_enough_liquidity_for_fok(self, order: Order) -> bool:
        """Check full immediate fill availability without mutating the book."""

        needed = order.quantity
        opposite_side = self._opposite_side(order.side)

        for price_ticks in self.book.price_levels(opposite_side):
            if not self._can_cross(order, price_ticks):
                break

            needed -= self.book.depth_at(opposite_side, price_ticks)
            if needed <= 0:
                return True

        return False

    def _create_trade(self, order: Order, resting_order: BookOrder, quantity: int) -> Trade:
        """Create a trade record from one incoming order and one resting order."""

        if order.side == Side.BUY:
            buyer_order_id = order.order_id
            seller_order_id = resting_order.order_id
        else:
            buyer_order_id = resting_order.order_id
            seller_order_id = order.order_id

        trade = Trade(
            trade_id=self.next_trade_id,
            price_ticks=resting_order.price_ticks,
            quantity=quantity,
            buyer_order_id=buyer_order_id,
            seller_order_id=seller_order_id,
            aggressor_order_id=order.order_id,
            resting_order_id=resting_order.order_id,
            aggressor_side=order.side,
            timestamp=order.timestamp,
        )
        self.next_trade_id += 1
        return trade

    def _should_rest_leftover(self, order: Order) -> bool:
        """Only regular limit orders can leave unfilled quantity in the book."""

        return order.order_type == OrderType.LIMIT and order.time_in_force == TimeInForce.GTC

    def _opposite_side(self, side: Side) -> Side:
        if side == Side.BUY:
            return Side.SELL

        return Side.BUY
