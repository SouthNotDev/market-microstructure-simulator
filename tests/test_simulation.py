import pytest

from market_sim import CancelOrder, Side, Simulation, SubmitLimitOrder, SubmitMarketOrder, TimeInForce


def test_simulation_processes_limit_and_market_events() -> None:
    simulation = Simulation()
    events = [
        SubmitLimitOrder(Side.SELL, quantity=25_000, price_ticks=10_010),
        SubmitMarketOrder(Side.BUY, quantity=10_000),
    ]

    result = simulation.run(events)

    assert result.processed_events == 2
    assert len(result.match_results) == 2
    assert len(result.trades) == 1
    assert result.trades[0].price_ticks == 10_010
    assert result.trades[0].quantity == 10_000
    assert result.snapshots[-1].ask_depth == ((10_010, 15_000),)


def test_simulation_records_no_trade_resting_limit_order() -> None:
    simulation = Simulation()

    result = simulation.run([
        SubmitLimitOrder(Side.BUY, quantity=25_000, price_ticks=10_000),
    ])

    assert result.processed_events == 1
    assert result.match_results[0].trades == ()
    assert result.snapshots[0].best_bid == 10_000
    assert result.snapshots[0].bid_depth == ((10_000, 25_000),)


def test_simulation_processes_cancel_event() -> None:
    simulation = Simulation()
    events = [
        SubmitLimitOrder(Side.BUY, quantity=25_000, price_ticks=10_000),
        CancelOrder(order_id=1),
    ]

    result = simulation.run(events)

    assert result.processed_events == 2
    assert len(result.cancel_results) == 1
    assert result.cancel_results[0].accepted is True
    assert result.cancel_results[0].canceled_quantity == 25_000
    assert result.snapshots[-1].best_bid is None


def test_simulation_supports_ioc_limit_event() -> None:
    simulation = Simulation()
    events = [
        SubmitLimitOrder(Side.SELL, quantity=10_000, price_ticks=10_010),
        SubmitLimitOrder(
            Side.BUY,
            quantity=25_000,
            price_ticks=10_010,
            time_in_force=TimeInForce.IOC,
        ),
    ]

    result = simulation.run(events)

    assert result.match_results[1].filled_quantity == 10_000
    assert result.match_results[1].canceled_quantity == 15_000
    assert result.snapshots[-1].best_bid is None
    assert result.snapshots[-1].best_ask is None


def test_simulation_max_events_stops_early() -> None:
    simulation = Simulation()
    events = [
        SubmitLimitOrder(Side.BUY, quantity=25_000, price_ticks=10_000),
        SubmitLimitOrder(Side.SELL, quantity=25_000, price_ticks=10_010),
    ]

    result = simulation.run(events, max_events=1)

    assert result.processed_events == 1
    assert len(result.match_results) == 1
    assert simulation.exchange.next_order_id == 2
    assert simulation.exchange.book.best_bid == 10_000
    assert simulation.exchange.book.best_ask is None


def test_simulation_can_process_single_event_incrementally() -> None:
    simulation = Simulation()

    first = simulation.process_event(SubmitLimitOrder(Side.SELL, quantity=25_000, price_ticks=10_010))
    second = simulation.process_event(SubmitMarketOrder(Side.BUY, quantity=10_000))

    assert first.incoming_order_id == 1
    assert second.incoming_order_id == 2
    assert len(simulation.recorder.snapshots) == 2
    assert simulation.recorder.trades[0].quantity == 10_000


def test_simulation_rejects_negative_max_events() -> None:
    simulation = Simulation()

    with pytest.raises(ValueError, match="max_events cannot be negative"):
        simulation.run([], max_events=-1)
