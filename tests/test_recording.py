from decimal import Decimal

import pytest

from market_sim import BookSnapshot, Exchange, Recorder, Side


def test_record_match_stores_result_trades_and_snapshot() -> None:
    exchange = Exchange()
    recorder = Recorder()
    exchange.submit_limit_order(Side.SELL, quantity=25_000, price_ticks=10_010)

    result = exchange.submit_market_order(Side.BUY, quantity=10_000)
    snapshot = recorder.record_match(result, exchange.book)

    assert recorder.match_results == [result]
    assert recorder.trades == list(result.trades)
    assert recorder.snapshots == [snapshot]
    assert snapshot.timestamp == 2
    assert snapshot.best_ask == 10_010
    assert snapshot.ask_depth == ((10_010, 15_000),)


def test_record_match_handles_no_trade_resting_order() -> None:
    exchange = Exchange()
    recorder = Recorder()

    result = exchange.submit_limit_order(Side.BUY, quantity=25_000, price_ticks=10_000)
    snapshot = recorder.record_match(result, exchange.book)

    assert result.trades == ()
    assert snapshot.timestamp == 1
    assert snapshot.best_bid == 10_000
    assert snapshot.bid_depth == ((10_000, 25_000),)


def test_record_cancel_stores_cancel_result_and_snapshot() -> None:
    exchange = Exchange()
    recorder = Recorder()
    exchange.submit_limit_order(Side.BUY, quantity=25_000, price_ticks=10_000)

    result = exchange.cancel_order(1)
    snapshot = recorder.record_cancel(result, exchange.book)

    assert recorder.cancel_results == [result]
    assert recorder.snapshots == [snapshot]
    assert snapshot.timestamp == 2
    assert snapshot.best_bid is None
    assert snapshot.bid_depth == ()


def test_snapshot_records_top_of_book_spread_mid_and_depth() -> None:
    exchange = Exchange()
    recorder = Recorder()
    exchange.submit_limit_order(Side.BUY, quantity=25_000, price_ticks=10_000)
    exchange.submit_limit_order(Side.BUY, quantity=10_000, price_ticks=9_995)
    exchange.submit_limit_order(Side.SELL, quantity=30_000, price_ticks=10_010)
    exchange.submit_limit_order(Side.SELL, quantity=15_000, price_ticks=10_015)

    snapshot = recorder.snapshot(exchange.book, timestamp=5)

    assert snapshot.best_bid == 10_000
    assert snapshot.best_ask == 10_010
    assert snapshot.spread == 10
    assert snapshot.mid_price == Decimal("10005")
    assert snapshot.bid_depth == ((10_000, 25_000), (9_995, 10_000))
    assert snapshot.ask_depth == ((10_010, 30_000), (10_015, 15_000))


def test_snapshot_is_immutable_after_book_changes() -> None:
    exchange = Exchange()
    recorder = Recorder()
    exchange.submit_limit_order(Side.SELL, quantity=25_000, price_ticks=10_010)

    snapshot = recorder.snapshot(exchange.book, timestamp=1)
    exchange.submit_market_order(Side.BUY, quantity=25_000)

    assert snapshot.ask_depth == ((10_010, 25_000),)
    assert snapshot.best_ask == 10_010
    assert exchange.book.best_ask is None


def test_book_snapshot_rejects_invalid_timestamp() -> None:
    with pytest.raises(ValueError, match="Snapshot timestamp must be positive"):
        BookSnapshot(
            timestamp=0,
            best_bid=None,
            best_ask=None,
            spread=None,
            mid_price=None,
            bid_depth=(),
            ask_depth=(),
        )
