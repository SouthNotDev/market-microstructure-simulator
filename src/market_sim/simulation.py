"""Event-driven simulation orchestration.

The simulation layer coordinates the existing components. It does not match
orders itself, store liquidity itself, or record history itself. Instead, it
feeds intent events into Exchange and asks Recorder to save the results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from market_sim.domain import CancelResult, MatchResult, Side, TimeInForce, Trade
from market_sim.exchange import Exchange
from market_sim.recording import BookSnapshot, Recorder


@dataclass(frozen=True)
class SubmitLimitOrder:
    """Intent to submit a limit order before exchange ID/timestamp assignment."""

    side: Side
    quantity: int
    price_ticks: int
    time_in_force: TimeInForce = TimeInForce.GTC


@dataclass(frozen=True)
class SubmitMarketOrder:
    """Intent to submit a market order before exchange ID/timestamp assignment."""

    side: Side
    quantity: int


@dataclass(frozen=True)
class CancelOrder:
    """Intent to cancel a live resting order by ID."""

    order_id: int


MarketEvent: TypeAlias = SubmitLimitOrder | SubmitMarketOrder | CancelOrder


@dataclass(frozen=True)
class SimulationResult:
    """Immutable summary of one simulation run."""

    processed_events: int
    match_results: tuple[MatchResult, ...]
    cancel_results: tuple[CancelResult, ...]
    trades: tuple[Trade, ...]
    snapshots: tuple[BookSnapshot, ...]

    def __post_init__(self) -> None:
        if self.processed_events < 0:
            raise ValueError("Processed events cannot be negative")


@dataclass
class Simulation:
    """Orchestrates event processing through Exchange and Recorder."""

    exchange: Exchange = field(default_factory=Exchange)
    recorder: Recorder = field(default_factory=Recorder)

    def run(self, events: list[MarketEvent] | tuple[MarketEvent, ...], max_events: int | None = None) -> SimulationResult:
        """Process a deterministic sequence of market events.

        This is intentionally finite and deterministic. Later, event sources and
        agents can feed events into this same processing path.
        """

        if max_events is not None and max_events < 0:
            raise ValueError("max_events cannot be negative")

        processed_events = 0
        for event in events:
            if max_events is not None and processed_events >= max_events:
                break

            self.process_event(event)
            processed_events += 1

        return SimulationResult(
            processed_events=processed_events,
            match_results=tuple(self.recorder.match_results),
            cancel_results=tuple(self.recorder.cancel_results),
            trades=tuple(self.recorder.trades),
            snapshots=tuple(self.recorder.snapshots),
        )

    def process_event(self, event: MarketEvent) -> MatchResult | CancelResult:
        """Process one intent event and record the post-event market state."""

        if isinstance(event, SubmitLimitOrder):
            result = self.exchange.submit_limit_order(
                side=event.side,
                quantity=event.quantity,
                price_ticks=event.price_ticks,
                time_in_force=event.time_in_force,
            )
            self.recorder.record_match(result, self.exchange.book)
            return result

        if isinstance(event, SubmitMarketOrder):
            result = self.exchange.submit_market_order(
                side=event.side,
                quantity=event.quantity,
            )
            self.recorder.record_match(result, self.exchange.book)
            return result

        if isinstance(event, CancelOrder):
            result = self.exchange.cancel_order(event.order_id)
            self.recorder.record_cancel(result, self.exchange.book)
            return result

        raise TypeError(f"Unsupported market event: {event!r}")

    def current_observation(self) -> BookSnapshot:
        """Return the current book state as an agent observation.

        We use the exchange's current event timestamp as the observation
        timestamp. That means the observation is marked with the timestamp that
        would be assigned to the next exchange event.
        """

        return self.recorder.snapshot(self.exchange.book, self.exchange.next_timestamp)

    def run_agent_steps(self, agents: list[object], max_steps: int) -> SimulationResult:
        """Ask agents for actions over a finite number of decision steps.

        Each step:

        1. Build a current observation from the live book.
        2. Ask each agent to decide based on that observation.
        3. Process every emitted event through the normal simulation path.

        This is still deterministic and finite. It is the bridge between fixed
        event-list simulation and future always-on agent simulations.
        """

        if max_steps < 0:
            raise ValueError("max_steps cannot be negative")

        processed_events = 0
        for _ in range(max_steps):
            observation = self.current_observation()
            step_events: list[MarketEvent] = []

            for agent in agents:
                step_events.extend(agent.decide(observation))

            if not step_events:
                break

            for event in step_events:
                self.process_event(event)
                processed_events += 1

        return SimulationResult(
            processed_events=processed_events,
            match_results=tuple(self.recorder.match_results),
            cancel_results=tuple(self.recorder.cancel_results),
            trades=tuple(self.recorder.trades),
            snapshots=tuple(self.recorder.snapshots),
        )
