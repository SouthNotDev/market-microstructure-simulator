import pytest

from market_sim import CancelResult, MatchResult, Order, OrderType, Side, TimeInForce, Trade


def test_limit_order_requires_price_ticks() -> None:
    with pytest.raises(ValueError, match="Limit orders must have a price"):
        Order(
            order_id=1,
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=25_000,
            timestamp=1,
        )


def test_market_order_rejects_price_ticks() -> None:
    with pytest.raises(ValueError, match="Market orders should not have a limit price"):
        Order(
            order_id=1,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=25_000,
            timestamp=1,
            price_ticks=10_010,
            time_in_force=TimeInForce.IOC,
        )


def test_market_order_cannot_use_gtc() -> None:
    with pytest.raises(ValueError, match="Market orders cannot rest"):
        Order(
            order_id=1,
            side=Side.SELL,
            order_type=OrderType.MARKET,
            quantity=25_000,
            timestamp=1,
        )


def test_valid_regular_limit_order() -> None:
    order = Order(
        order_id=1,
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=25_000,
        timestamp=1,
        price_ticks=10_010,
    )

    assert order.quantity == 25_000
    assert order.price_ticks == 10_010
    assert order.time_in_force == TimeInForce.GTC


def test_order_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValueError, match="Order quantity must be positive"):
        Order(
            order_id=1,
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=0,
            timestamp=1,
            price_ticks=10_010,
        )


def test_trade_records_buyer_seller_and_aggressor_context() -> None:
    trade = Trade(
        trade_id=1,
        price_ticks=10_010,
        quantity=25_000,
        buyer_order_id=2,
        seller_order_id=1,
        aggressor_order_id=2,
        resting_order_id=1,
        aggressor_side=Side.BUY,
        timestamp=2,
    )

    assert trade.buyer_order_id == 2
    assert trade.seller_order_id == 1
    assert trade.aggressor_order_id == 2
    assert trade.resting_order_id == 1
    assert trade.aggressor_side == Side.BUY


def test_trade_rejects_inconsistent_buy_aggressor() -> None:
    with pytest.raises(ValueError, match="Buy aggressor must be the buyer order"):
        Trade(
            trade_id=1,
            price_ticks=10_010,
            quantity=25_000,
            buyer_order_id=2,
            seller_order_id=1,
            aggressor_order_id=1,
            resting_order_id=2,
            aggressor_side=Side.BUY,
            timestamp=2,
        )


def test_match_result_filled_quantity_must_equal_trade_quantity() -> None:
    trade = Trade(
        trade_id=1,
        price_ticks=10_010,
        quantity=25_000,
        buyer_order_id=2,
        seller_order_id=1,
        aggressor_order_id=2,
        resting_order_id=1,
        aggressor_side=Side.BUY,
        timestamp=2,
    )

    with pytest.raises(ValueError, match="Filled quantity must equal total trade quantity"):
        MatchResult(
            incoming_order_id=2,
            timestamp=2,
            trades=(trade,),
            filled_quantity=20_000,
        )


def test_match_result_allows_resting_remainder() -> None:
    result = MatchResult(
        incoming_order_id=2,
        timestamp=2,
        filled_quantity=0,
        canceled_quantity=0,
        resting_quantity=25_000,
        resting_order_id=2,
    )

    assert result.resting_quantity == 25_000
    assert result.resting_order_id == 2


def test_cancel_result_requires_positive_quantity_when_accepted() -> None:
    with pytest.raises(ValueError, match="Accepted cancels must remove positive quantity"):
        CancelResult(
            order_id=1,
            accepted=True,
            canceled_quantity=0,
            timestamp=1,
        )


def test_cancel_result_rejected_cancel_has_zero_quantity() -> None:
    result = CancelResult(
        order_id=1,
        accepted=False,
        canceled_quantity=0,
        timestamp=1,
    )

    assert result.accepted is False
    assert result.canceled_quantity == 0
