from market_sim import MatchingEngine, Order, OrderBook, OrderType, Side, TimeInForce


def limit_order(
    order_id: int,
    side: Side,
    price_ticks: int,
    quantity: int = 25_000,
    timestamp: int | None = None,
    time_in_force: TimeInForce = TimeInForce.GTC,
) -> Order:
    return Order(
        order_id=order_id,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        timestamp=timestamp or order_id,
        price_ticks=price_ticks,
        time_in_force=time_in_force,
    )


def market_order(
    order_id: int,
    side: Side,
    quantity: int,
    timestamp: int | None = None,
) -> Order:
    return Order(
        order_id=order_id,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        timestamp=timestamp or order_id,
        time_in_force=TimeInForce.IOC,
    )


def test_buy_market_order_partially_fills_best_ask() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))
    engine = MatchingEngine(book)

    result = engine.process_order(market_order(2, Side.BUY, quantity=10_000))

    assert result.filled_quantity == 10_000
    assert result.canceled_quantity == 0
    assert result.resting_quantity == 0
    assert len(result.trades) == 1
    assert result.trades[0].price_ticks == 10_010
    assert result.trades[0].quantity == 10_000
    assert result.trades[0].buyer_order_id == 2
    assert result.trades[0].seller_order_id == 1
    assert result.trades[0].aggressor_side == Side.BUY
    assert book.depth_at(Side.SELL, 10_010) == 15_000


def test_sell_market_order_matches_highest_bid_first() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.BUY, 10_000, quantity=25_000))
    book.add_resting_order(limit_order(2, Side.BUY, 10_005, quantity=25_000))
    engine = MatchingEngine(book)

    result = engine.process_order(market_order(3, Side.SELL, quantity=10_000))

    assert result.filled_quantity == 10_000
    assert result.trades[0].price_ticks == 10_005
    assert result.trades[0].buyer_order_id == 2
    assert result.trades[0].seller_order_id == 3
    assert result.trades[0].aggressor_side == Side.SELL
    assert book.depth_at(Side.BUY, 10_005) == 15_000
    assert book.depth_at(Side.BUY, 10_000) == 25_000


def test_market_order_walks_price_levels_and_cancels_unfilled_remainder() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=10_000))
    book.add_resting_order(limit_order(2, Side.SELL, 10_011, quantity=15_000))
    engine = MatchingEngine(book)

    result = engine.process_order(market_order(3, Side.BUY, quantity=30_000))

    assert result.filled_quantity == 25_000
    assert result.canceled_quantity == 5_000
    assert [trade.price_ticks for trade in result.trades] == [10_010, 10_011]
    assert [trade.quantity for trade in result.trades] == [10_000, 15_000]
    assert book.best_ask is None


def test_crossing_gtc_buy_limit_rests_leftover_as_bid() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))
    engine = MatchingEngine(book)

    result = engine.process_order(
        limit_order(2, Side.BUY, 10_010, quantity=30_000, time_in_force=TimeInForce.GTC)
    )

    assert result.filled_quantity == 25_000
    assert result.resting_quantity == 5_000
    assert result.resting_order_id == 2
    assert result.canceled_quantity == 0
    assert book.best_ask is None
    assert book.best_bid == 10_010
    assert book.depth_at(Side.BUY, 10_010) == 5_000


def test_non_crossing_gtc_limit_order_rests_without_trade() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))
    engine = MatchingEngine(book)

    result = engine.process_order(
        limit_order(2, Side.BUY, 10_008, quantity=30_000, time_in_force=TimeInForce.GTC)
    )

    assert result.trades == ()
    assert result.filled_quantity == 0
    assert result.resting_quantity == 30_000
    assert book.best_bid == 10_008
    assert book.best_ask == 10_010


def test_ioc_limit_order_cancels_leftover() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))
    engine = MatchingEngine(book)

    result = engine.process_order(
        limit_order(2, Side.BUY, 10_010, quantity=30_000, time_in_force=TimeInForce.IOC)
    )

    assert result.filled_quantity == 25_000
    assert result.canceled_quantity == 5_000
    assert result.resting_quantity == 0
    assert book.best_bid is None
    assert book.best_ask is None


def test_fok_limit_order_cancels_everything_if_full_fill_is_not_available() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=25_000))
    engine = MatchingEngine(book)

    result = engine.process_order(
        limit_order(2, Side.BUY, 10_010, quantity=30_000, time_in_force=TimeInForce.FOK)
    )

    assert result.trades == ()
    assert result.filled_quantity == 0
    assert result.canceled_quantity == 30_000
    assert book.depth_at(Side.SELL, 10_010) == 25_000


def test_fok_limit_order_executes_if_full_fill_is_available() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=10_000))
    book.add_resting_order(limit_order(2, Side.SELL, 10_011, quantity=15_000))
    engine = MatchingEngine(book)

    result = engine.process_order(
        limit_order(3, Side.BUY, 10_011, quantity=25_000, time_in_force=TimeInForce.FOK)
    )

    assert result.filled_quantity == 25_000
    assert result.canceled_quantity == 0
    assert [trade.price_ticks for trade in result.trades] == [10_010, 10_011]
    assert book.best_ask is None


def test_matching_respects_fifo_at_same_price() -> None:
    book = OrderBook()
    book.add_resting_order(limit_order(1, Side.SELL, 10_010, quantity=10_000, timestamp=1))
    book.add_resting_order(limit_order(2, Side.SELL, 10_010, quantity=10_000, timestamp=2))
    engine = MatchingEngine(book)

    result = engine.process_order(market_order(3, Side.BUY, quantity=15_000))

    assert [trade.resting_order_id for trade in result.trades] == [1, 2]
    assert [trade.quantity for trade in result.trades] == [10_000, 5_000]
    assert book.depth_at(Side.SELL, 10_010) == 5_000
    assert book.orders_at(Side.SELL, 10_010)[0].order_id == 2
