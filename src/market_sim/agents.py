"""Agent interfaces and simple agent implementations.

Agents observe market state and emit intent events. They do not mutate the
order book, matching engine, or exchange directly.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from market_sim.recording import BookSnapshot
from market_sim.simulation import MarketEvent


class Agent(Protocol):
    """Interface for anything that can act inside the simulation.

    The first observation type is `BookSnapshot`. It gives the agent a clean
    view of the current book without exposing internal dictionaries/deques.
    """

    def decide(self, observation: BookSnapshot) -> list[MarketEvent]:
        """Return zero or more intent events based on the current observation."""


@dataclass
class ScriptedAgent:
    """Agent that emits a predefined sequence of events.

    This is intentionally not intelligent. Its purpose is to test and explain
    the agent/simulation interaction before we build a strategy.
    """

    events: deque[MarketEvent] | list[MarketEvent] | tuple[MarketEvent, ...]
    observations: list[BookSnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Convert the input sequence to a deque so we can efficiently pop the
        # next event from the left/front each time the agent acts.
        if not isinstance(self.events, deque):
            self.events = deque(self.events)

    def decide(self, observation: BookSnapshot) -> list[MarketEvent]:
        """Record what the agent saw, then emit the next scripted event."""

        self.observations.append(observation)

        if not self.events:
            return []

        return [self.events.popleft()]
