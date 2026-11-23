"""Small, explicit traffic-control MDP for Value/Policy Iteration.

This is a *planning approximation*, not the browser's car-by-car simulator.
Each step is one decision interval. Queue counts are capped; arrivals are
independent truncated Poisson counts; service is deterministic. Parameters
are deliberately visible to make the model inspectable in the TD.
"""

from dataclasses import dataclass
from itertools import product
from math import exp, factorial, isclose

KEEP = "KEEP"
SWITCH = "SWITCH"
ACTIONS = (KEEP, SWITCH)
State = tuple[int, int, int, int]  # NS queue, EW queue, green axis (0=NS), cooldown


@dataclass(frozen=True)
class MDPConfig:
    max_queue: int = 10
    arrival_rate: float = 0.8  # expected arrivals per axis per decision step
    service_capacity: int = 2  # departures per green axis per step
    switch_lost_steps: int = 1  # no service on a switching step
    switch_penalty: float = 0.0
    max_arrivals: int = 3  # tail mass folded into this final bucket

    def __post_init__(self):
        if self.max_queue < 1 or self.service_capacity < 1:
            raise ValueError("Queue capacity and service capacity must be positive")
        if self.arrival_rate < 0 or self.max_arrivals < 1:
            raise ValueError("Arrival rate must be nonnegative; max_arrivals positive")
        if self.switch_lost_steps < 1:
            raise ValueError("switch_lost_steps must be at least one")
        if self.switch_penalty < 0:
            raise ValueError("switch_penalty must be nonnegative")


class TrafficMDP:
    def __init__(self, config: MDPConfig = MDPConfig()):
        self.config = config
        self.states: tuple[State, ...] = tuple(
            product(
                range(config.max_queue + 1),
                range(config.max_queue + 1),
                range(2),
                range(config.switch_lost_steps),
            )
        )
        self.state_set = set(self.states)
        self.arrival_distribution = self._arrival_distribution()

    def _arrival_distribution(self) -> tuple[tuple[int, float], ...]:
        cfg = self.config
        probabilities = [
            exp(-cfg.arrival_rate) * cfg.arrival_rate**k / factorial(k)
            for k in range(cfg.max_arrivals)
        ]
        probabilities.append(max(0.0, 1.0 - sum(probabilities)))
        return tuple((k, p) for k, p in enumerate(probabilities) if p > 0)

    def valid_actions(self, state: State) -> tuple[str, ...]:
        self._check_state(state)
        return (KEEP,) if state[3] > 0 else ACTIONS

    def _check_state(self, state: State) -> None:
        if state not in self.state_set:
            raise ValueError(f"Invalid MDP state: {state}")

    def transitions(
        self, state: State, action: str
    ) -> tuple[tuple[float, State, float], ...]:
        """Return (probability, next_state, reward) for one decision interval.

        The reward is negative queue-time: the sum of queues after service
        and arrivals, with an optional switch penalty. Capping queues loses
        overflow cars; this is an intentional approximation.
        """
        if action not in self.valid_actions(state):
            raise ValueError(f"Action {action!r} invalid for state {state}")
        q_ns, q_ew, green, cooldown = state
        cfg = self.config
        if cooldown:
            next_green, next_cooldown = green, cooldown - 1
            departures = 0
        elif action == SWITCH:
            next_green, next_cooldown = 1 - green, cfg.switch_lost_steps - 1
            departures = 0
        else:
            next_green, next_cooldown = green, 0
            departures = cfg.service_capacity

        served_ns = (
            min(q_ns, departures)
            if green == 0 and action == KEEP and not cooldown
            else 0
        )
        served_ew = (
            min(q_ew, departures)
            if green == 1 and action == KEEP and not cooldown
            else 0
        )
        after_ns, after_ew = q_ns - served_ns, q_ew - served_ew

        aggregated: dict[State, float] = {}
        for arrivals_ns, p_ns in self.arrival_distribution:
            for arrivals_ew, p_ew in self.arrival_distribution:
                successor = (
                    min(cfg.max_queue, after_ns + arrivals_ns),
                    min(cfg.max_queue, after_ew + arrivals_ew),
                    next_green,
                    next_cooldown,
                )
                aggregated[successor] = aggregated.get(successor, 0.0) + p_ns * p_ew

        penalty = cfg.switch_penalty if action == SWITCH else 0.0
        return tuple(
            (probability, successor, -(successor[0] + successor[1]) - penalty)
            for successor, probability in aggregated.items()
        )

    def validate(self) -> None:
        for state in self.states:
            for action in self.valid_actions(state):
                transitions = self.transitions(state, action)
                if not isclose(sum(p for p, _, _ in transitions), 1.0, abs_tol=1e-10):
                    raise AssertionError(
                        f"Probabilities do not sum to one: {state}, {action}"
                    )
                if any(
                    p < 0 or successor not in self.state_set
                    for p, successor, _ in transitions
                ):
                    raise AssertionError(f"Invalid transition: {state}, {action}")

    def describe(self) -> dict:
        cfg = self.config
        return {
            "state_fields": [
                "north_south_queue",
                "east_west_queue",
                "green_axis",
                "switch_cooldown",
            ],
            "actions": list(ACTIONS),
            "state_count": len(self.states),
            "max_queue": cfg.max_queue,
            "arrival_rate_per_axis_per_step": cfg.arrival_rate,
            "service_capacity_per_step": cfg.service_capacity,
            "switch_lost_steps": cfg.switch_lost_steps,
            "reward": "-(next_ns_queue + next_ew_queue) - switch_penalty",
            "notes": [
                "Approximate decision-step model; not the exact browser simulation.",
                "Arrivals are independent truncated Poisson random variables.",
                "Queue counts are capped and overflow is not represented.",
                "Switch consumes a decision step without service.",
            ],
        }
