from market_sim import ScriptedAgent, Side, Simulation, SubmitLimitOrder, SubmitMarketOrder


def test_scripted_agent_records_observations_and_emits_events() -> None:
    agent = ScriptedAgent([
        SubmitLimitOrder(Side.SELL, quantity=25_000, price_ticks=10_010),
    ])
    simulation = Simulation()

    result = simulation.run_agent_steps([agent], max_steps=1)

    assert result.processed_events == 1
    assert len(agent.observations) == 1
    assert agent.observations[0].best_bid is None
    assert agent.observations[0].best_ask is None
    assert result.snapshots[-1].ask_depth == ((10_010, 25_000),)


def test_agent_steps_see_book_state_created_by_previous_steps() -> None:
    agent = ScriptedAgent([
        SubmitLimitOrder(Side.SELL, quantity=25_000, price_ticks=10_010),
        SubmitMarketOrder(Side.BUY, quantity=10_000),
    ])
    simulation = Simulation()

    result = simulation.run_agent_steps([agent], max_steps=2)

    assert result.processed_events == 2
    assert len(agent.observations) == 2
    assert agent.observations[0].ask_depth == ()
    assert agent.observations[1].ask_depth == ((10_010, 25_000),)
    assert result.snapshots[-1].ask_depth == ((10_010, 15_000),)
    assert result.trades[0].quantity == 10_000


def test_agent_loop_stops_when_agents_emit_no_events() -> None:
    agent = ScriptedAgent([])
    simulation = Simulation()

    result = simulation.run_agent_steps([agent], max_steps=5)

    assert result.processed_events == 0
    assert len(agent.observations) == 1
    assert result.snapshots == ()


def test_agent_loop_respects_max_steps() -> None:
    agent = ScriptedAgent([
        SubmitLimitOrder(Side.BUY, quantity=10_000, price_ticks=10_000),
        SubmitLimitOrder(Side.BUY, quantity=10_000, price_ticks=9_995),
    ])
    simulation = Simulation()

    result = simulation.run_agent_steps([agent], max_steps=1)

    assert result.processed_events == 1
    assert len(agent.observations) == 1
    assert simulation.exchange.book.best_bid == 10_000
    assert len(agent.events) == 1
