from market_sim import Exchange, Side, TimeInForce


def test_exchange_assigns_order_ids_and_timestamps_to_limit_orders() -> None:
    exchange = Exchange()

    first = exchange.submit_limit_order(Side.BUY, quantity=25_000, price_ticks=10_000)
    second = exchange.submit_limit_order(Side.SELL, quantity=30_000, price_ticks=10_010)

    assert first.incoming_order_id == 1
    assert first.resting_order_id == 1
    assert second.incoming_order_id == 2
    assert second.resting_order_id == 2
    assert exchange.next_order_id == 3
    assert exchange.next_timestamp == 3
    assert exchange.book.orders_at(Side.BUY, 10_000)[0].timestamp == 1
    assert exchange.book.orders_at(Side.SELL, 10_010)[0].timestamp == 2


def test_exchange_market_order_matches_existing_liquidity() -> None:
    exchange = Exchange()
    exchange.submit_limit_order(Side.SELL, quantity=25_000, price_ticks=10_010)

    result = exchange.submit_market_order(Side.BUY, quantity=10_000)

    assert result.incoming_order_id == 2
    assert result.filled_quantity == 10_000
    assert result.trades[0].trade_id == 1
    assert result.trades[0].buyer_order_id == 2
    assert result.trades[0].seller_order_id == 1
    assert result.trades[0].timestamp == 2
    assert exchange.book.depth_at(Side.SELL, 10_010) == 15_000


def test_exchange_submit_limit_order_supports_ioc() -> None:
    exchange = Exchange()
    exchange.submit_limit_order(Side.SELL, quantity=10_000, price_ticks=10_010)

    result = exchange.submit_limit_order(
        Side.BUY,
        quantity=25_000,
        price_ticks=10_010,
        time_in_force=TimeInForce.IOC,
    )

    assert result.incoming_order_id == 2
    assert result.filled_quantity == 10_000
    assert result.canceled_quantity == 15_000
    assert result.resting_quantity == 0
    assert exchange.book.best_bid is None


def test_exchange_cancel_existing_order_returns_accepted_result() -> None:
    exchange = Exchange()
    exchange.submit_limit_order(Side.BUY, quantity=25_000, price_ticks=10_000)

    result = exchange.cancel_order(1)

    assert result.order_id == 1
    assert result.accepted is True
    assert result.canceled_quantity == 25_000
    assert result.timestamp == 2
    assert exchange.book.best_bid is None
    assert exchange.next_order_id == 2
    assert exchange.next_timestamp == 3


def test_exchange_cancel_missing_order_returns_rejected_result() -> None:
    exchange = Exchange()

    result = exchange.cancel_order(999)

    assert result.order_id == 999
    assert result.accepted is False
    assert result.canceled_quantity == 0
    assert result.timestamp == 1
    assert exchange.next_order_id == 1
    assert exchange.next_timestamp == 2


def test_exchange_cancel_after_partial_fill_uses_remaining_quantity() -> None:
    exchange = Exchange()
    exchange.submit_limit_order(Side.SELL, quantity=25_000, price_ticks=10_010)
    exchange.submit_market_order(Side.BUY, quantity=10_000)

    result = exchange.cancel_order(1)

    assert result.accepted is True
    assert result.canceled_quantity == 15_000
    assert result.timestamp == 3
    assert exchange.book.best_ask is None
