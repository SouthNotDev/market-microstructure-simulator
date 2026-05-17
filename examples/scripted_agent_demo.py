"""Run a small scripted-agent simulation and print what the agent observes."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_sim import ScriptedAgent, Side, Simulation, SubmitLimitOrder, SubmitMarketOrder


def format_depth(depth: tuple[tuple[int, int], ...]) -> str:
    if not depth:
        return "empty"

    return ", ".join(f"{quantity}@{price}" for price, quantity in depth)


def main() -> None:
    agent = ScriptedAgent(
        [
            SubmitLimitOrder(Side.SELL, quantity=25_000, price_ticks=10_010),
            SubmitLimitOrder(Side.BUY, quantity=20_000, price_ticks=10_000),
            SubmitLimitOrder(Side.SELL, quantity=15_000, price_ticks=10_015),
            SubmitMarketOrder(Side.BUY, quantity=10_000),
            SubmitMarketOrder(Side.SELL, quantity=5_000),
        ]
    )
    simulation = Simulation()
    result = simulation.run_agent_steps([agent], max_steps=10)

    print("Scripted agent observations before each emitted event:")
    for step, observation in enumerate(agent.observations, start=1):
        print(f"\nStep {step}")
        print(f"  timestamp: {observation.timestamp}")
        print(f"  best_bid: {observation.best_bid}")
        print(f"  best_ask: {observation.best_ask}")
        print(f"  spread: {observation.spread}")
        print(f"  mid_price: {observation.mid_price}")
        print(f"  bid_depth: {format_depth(observation.bid_depth)}")
        print(f"  ask_depth: {format_depth(observation.ask_depth)}")

    print("\nSimulation result:")
    print(f"  processed_events: {result.processed_events}")
    print(f"  trades: {len(result.trades)}")
    for trade in result.trades:
        print(
            "  "
            f"trade_id={trade.trade_id} "
            f"price={trade.price_ticks} "
            f"quantity={trade.quantity} "
            f"aggressor={trade.aggressor_side.value} "
            f"resting_order_id={trade.resting_order_id}"
        )

    final_snapshot = result.snapshots[-1]
    print("\nFinal book snapshot:")
    print(f"  best_bid: {final_snapshot.best_bid}")
    print(f"  best_ask: {final_snapshot.best_ask}")
    print(f"  bid_depth: {format_depth(final_snapshot.bid_depth)}")
    print(f"  ask_depth: {format_depth(final_snapshot.ask_depth)}")


if __name__ == "__main__":
    main()
