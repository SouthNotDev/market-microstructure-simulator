from decimal import Decimal

import pytest

from market_sim import BookOrder, Order, OrderBook, OrderType, Side, TimeInForce


def limit_order(
    order_id: int,
    side: Side,
    price_ticks: int,
    quantity: int = 25_000,
    timestamp: int | None = None,
) -> Order:
    return Order(
        order_id=order_id,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        timestamp=timestamp or order_id,
        price_ticks=price_ticks,
        time_in_force=TimeInForce.GTC,
    )


def test_book_stores_bid_and_ask_depth() -> None:
    book = OrderBook()

    book.add_resting_order(limit_order(1, Side.BUY, 10_000, quantity=25_000))
    book.add_resting_order(limit_order(2, Side.SELL, 10_010, quantity=30_000))

    assert book.depth_at(Side.BUY, 10_000) == 25_000
    assert book.depth_at(Side.SELL, 10_010) == 30_000


def test_best_bid_is_highest_bid_price() -> None:
    book = OrderBook()

    book.add_resting_order(limit_order(1, Side.BUY, 10_000))
    book.add_resting_order(limit_order(2, Side.BUY, 10_008))
    book.add_resting_order(limit_order(3, Side.BUY, 10_003))

    assert book.best_bid == 10_008
    assert book.price_levels(Side.BUY) == (10_008, 10_003, 10_000)


def test_best_ask_is_lowest_ask_price() -> None:
    book = OrderBook()

    book.add_resting_order(limit_order(1, Side.SELL, 10_020))
    book.add_resting_order(limit_order(2, Side.SELL, 10_010))
    book.add_resting_order(limit_order(3, Side.SELL, 10_015))

    assert book.best_ask == 10_010
    assert book.price_levels(Side.SELL) == (10_010, 10_015, 10_020)


def test_spread_and_mid_price_use_best_prices() -> None:
    book = OrderBook()

    book.add_resting_order(limit_order(1, Side.BUY, 10_000))
    book.add_resting_order(limit_order(2, Side.SELL, 10_011))

    assert book.spread == 11
    assert book.mid_price == Decimal("10005.5")


def test_missing_side_has_no_spread_or_mid_price() -> None:
    book = OrderBook()

    book.add_resting_order(limit_order(1, Side.BUY, 10_000))

    assert book.best_bid == 10_000
    assert book.best_ask is None
    assert book.spread is None
    assert book.mid_price is None


def test_orders_at_same_price_preserve_fifo_order() -> None:
    book = OrderBook()
    first = limit_order(1, Side.SELL, 10_010, quantity=10_000, timestamp=1)
    second = limit_order(2, Side.SELL, 10_010, quantity=40_000, timestamp=2)

    book.add_resting_order(first)
    book.add_resting_order(second)

    resting_orders = book.orders_at(Side.SELL, 10_010)

    assert [order.order_id for order in resting_orders] == [1, 2]
    assert [order.remaining_quantity for order in resting_orders] == [10_000, 40_000]
    assert book.depth_at(Side.SELL, 10_010) == 50_000


def test_add_resting_order_converts_order_to_live_book_order() -> None:
    book = OrderBook()
    original_order = limit_order(1, Side.BUY, 10_000, quantity=25_000, timestamp=7)

    book.add_resting_order(original_order)

    (book_order,) = book.orders_at(Side.BUY, 10_000)
    assert isinstance(book_order, BookOrder)
    assert book_order.order_id == original_order.order_id
    assert book_order.side == original_order.side
    assert book_order.price_ticks == original_order.price_ticks
    assert book_order.remaining_quantity == original_order.quantity
    assert book_order.timestamp == original_order.timestamp


def test_depth_uses_live_remaining_quantity() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))

    (book_order,) = book.orders_at(Side.SELL, 10_010)
    book_order.remaining_quantity = 5_000

    assert book.depth_at(Side.SELL, 10_010) == 5_000


def test_book_order_rejects_non_positive_remaining_quantity() -> None:
    with pytest.raises(ValueError, match="Book order remaining quantity must be positive"):
        BookOrder(
            order_id=1,
            side=Side.BUY,
            price_ticks=10_000,
            remaining_quantity=0,
            timestamp=1,
        )


def test_best_price_for_side_returns_side_priority_price() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.BUY, 10_000))
    book.add_resting_order(limit_order(2, Side.BUY, 10_005))
    book.add_resting_order(limit_order(3, Side.SELL, 10_020))
    book.add_resting_order(limit_order(4, Side.SELL, 10_015))

    assert book.best_price_for_side(Side.BUY) == 10_005
    assert book.best_price_for_side(Side.SELL) == 10_015


def test_peek_best_order_does_not_remove_liquidity() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))

    first_peek = book.peek_best_order(Side.SELL)
    second_peek = book.peek_best_order(Side.SELL)

    assert first_peek is second_peek
    assert first_peek is not None
    assert first_peek.order_id == 1
    assert book.depth_at(Side.SELL, 10_010) == 25_000


def test_peek_best_order_uses_price_priority_before_time_priority() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_020, timestamp=1))
    book.add_resting_order(limit_order(2, Side.SELL, 10_010, timestamp=2))

    best_order = book.peek_best_order(Side.SELL)

    assert best_order is not None
    assert best_order.order_id == 2
    assert best_order.price_ticks == 10_010


def test_remove_best_order_removes_fifo_order_at_best_price() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, timestamp=1))
    book.add_resting_order(limit_order(2, Side.SELL, 10_010, timestamp=2))

    removed = book.remove_best_order(Side.SELL)

    assert removed is not None
    assert removed.order_id == 1
    assert [order.order_id for order in book.orders_at(Side.SELL, 10_010)] == [2]


def test_remove_best_order_deletes_empty_price_level() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.BUY, 10_000))
    book.add_resting_order(limit_order(2, Side.BUY, 9_995))

    removed = book.remove_best_order(Side.BUY)

    assert removed is not None
    assert removed.order_id == 1
    assert book.depth_at(Side.BUY, 10_000) == 0
    assert book.best_bid == 9_995
    assert book.price_levels(Side.BUY) == (9_995,)


def test_remove_best_order_returns_none_when_side_is_empty() -> None:
    book = OrderBook()

    assert book.peek_best_order(Side.BUY) is None
    assert book.remove_best_order(Side.BUY) is None


def test_add_resting_order_indexes_order_id_for_cancellation() -> None:
    book = OrderBook()

    book.add_resting_order(limit_order(1, Side.BUY, 10_000))

    assert 1 in book.orders_by_id
    assert book.orders_by_id[1].side == Side.BUY
    assert book.orders_by_id[1].price_ticks == 10_000


def test_duplicate_resting_order_id_is_rejected() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.BUY, 10_000))

    with pytest.raises(ValueError, match="Order ID is already resting"):
        book.add_resting_order(limit_order(1, Side.SELL, 10_010))


def test_cancel_existing_bid_removes_live_quantity_and_index() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.BUY, 10_000, quantity=25_000))

    canceled = book.cancel_order(1)

    assert canceled is not None
    assert canceled.order_id == 1
    assert canceled.remaining_quantity == 25_000
    assert book.depth_at(Side.BUY, 10_000) == 0
    assert book.best_bid is None
    assert 1 not in book.orders_by_id


def test_cancel_existing_ask_removes_live_quantity_and_index() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))

    canceled = book.cancel_order(1)

    assert canceled is not None
    assert canceled.order_id == 1
    assert book.depth_at(Side.SELL, 10_010) == 0
    assert book.best_ask is None
    assert 1 not in book.orders_by_id


def test_cancel_middle_order_preserves_fifo_for_other_orders() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=10_000, timestamp=1))
    book.add_resting_order(limit_order(2, Side.SELL, 10_010, quantity=20_000, timestamp=2))
    book.add_resting_order(limit_order(3, Side.SELL, 10_010, quantity=30_000, timestamp=3))

    canceled = book.cancel_order(2)

    assert canceled is not None
    assert canceled.order_id == 2
    assert [order.order_id for order in book.orders_at(Side.SELL, 10_010)] == [1, 3]
    assert book.depth_at(Side.SELL, 10_010) == 40_000
    assert 2 not in book.orders_by_id


def test_cancel_nonexistent_order_returns_none() -> None:
    book = OrderBook()

    assert book.cancel_order(999) is None


def test_cancel_rejects_invalid_order_id() -> None:
    book = OrderBook()

    with pytest.raises(ValueError, match="Order ID must be positive"):
        book.cancel_order(0)


def test_remove_best_order_removes_order_from_index() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.BUY, 10_000))

    removed = book.remove_best_order(Side.BUY)

    assert removed is not None
    assert removed.order_id == 1
    assert 1 not in book.orders_by_id


def test_market_order_cannot_be_added_as_resting_liquidity() -> None:
    book = OrderBook()
    market_order = Order(
        order_id=1,
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=25_000,
        timestamp=1,
        time_in_force=TimeInForce.IOC,
    )

    with pytest.raises(ValueError, match="Only limit orders can rest"):
        book.add_resting_order(market_order)
