"""Exact dynamic-programming planners for the supplied finite TrafficMDP.

No Flask dependency. Iteration callbacks receive actual solver measurements.
"""

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from .mdp import TrafficMDP, State


@dataclass
class SolveResult:
    values: dict[State, float]
    policy: dict[State, str]
    history: list[dict]
    converged: bool
    iterations: int
    elapsed_seconds: float


def _validate(gamma: float, epsilon: float, max_iterations: int) -> None:
    if not 0 <= gamma < 1:
        raise ValueError("gamma must be in [0, 1)")
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")


def _prepare(mdp: TrafficMDP):
    """Cache transitions once; no repeated Poisson calculations per iteration."""
    return {
        s: {a: mdp.transitions(s, a) for a in mdp.valid_actions(s)} for s in mdp.states
    }


def _q(outcomes, values, gamma):
    # TODO 1: Compute Q(s,a) as the probability-weighted sum of
    # immediate rewards and discounted next-state values.
    total = 0.0
    for probability, successor, reward in outcomes:
        total += probability * (reward + gamma * values[successor])
    return total 


def action_values(
    mdp: TrafficMDP, state: State, values: dict[State, float], gamma: float
):
    """Q(s,a) for each valid action under a supplied value function."""
    if not 0 <= gamma < 1:
        raise ValueError("gamma must be in [0, 1)")
    return {
        a: _q(mdp.transitions(state, a), values, gamma)
        for a in mdp.valid_actions(state)
    }


def _greedy(actions, values, gamma):
    # Deterministic tie breaking: KEEP is listed first in the MDP.
    # TODO 2: Select the action with the highest Q-value using _q().
    # Preserve the existing action order to break ties deterministically.
    best_action = None
    best_q = float("-inf")
    for action, outcomes in actions.items():
        q_value = _q(outcomes, values, gamma)
        if q_value > best_q:
            best_action = action
            best_q = q_value
    return best_action




def value_iteration(
    mdp: TrafficMDP,
    gamma: float = 0.95,
    epsilon: float = 1e-3,
    max_iterations: int = 1000,
    on_iteration: Callable[[dict], None] | None = None,
) -> SolveResult:
    """Synchronous Bellman optimality updates; epsilon bounds the Bellman residual."""
    _validate(gamma, epsilon, max_iterations)
    start = perf_counter()
    transitions = _prepare(mdp)
    values = dict.fromkeys(mdp.states, 0.0)
    policy = {s: next(iter(transitions[s])) for s in mdp.states}
    history = []
    converged = False
    for iteration in range(1, max_iterations + 1):
        # TODO 3a: Apply one synchronous Bellman optimality update to
        # every state, using the *previous* values dictionary.
        # Store the resulting dictionary in `updated`.
        # Bellman optimality update, synchronized with the previous values.
        updated = {
            s: max(_q(outcomes, values, gamma) for outcomes in actions.values())
            for s, actions in transitions.items()
        }

        # TODO 3b: Compute the maximum absolute change in state values.
        # Store this scalar in `delta`.
        delta = max(abs(updated[s] - values[s]) for s in mdp.states)

        # TODO 3c: Extract a greedy policy from the updated values.
        # Store the state-to-action mapping in `new_policy`.
        new_policy = {
            s: _greedy(actions, updated, gamma)
            for s, actions in transitions.items()
        }
        changes = sum(new_policy[s] != policy[s] for s in mdp.states)
        values, policy = updated, new_policy
        record = {
            "iteration": iteration,
            "delta": delta,
            "policy_changes": changes,
            "elapsed_seconds": perf_counter() - start,
        }
        history.append(record)
        if on_iteration:
            on_iteration(record.copy())
        if delta < epsilon:
            converged = True
            break
    return SolveResult(
        values, policy, history, converged, len(history), perf_counter() - start
    )


def policy_iteration(
    mdp: TrafficMDP,
    gamma: float = 0.95,
    epsilon: float = 1e-3,
    max_iterations: int = 1000,
    evaluation_epsilon: float = 1e-5,
    max_evaluation_iterations: int = 10000,
    on_iteration: Callable[[dict], None] | None = None,
) -> SolveResult:
    """Iterative policy evaluation followed by greedy policy improvement.

    evaluation_epsilon controls evaluation precision; max_iterations limits
    outer policy-improvement passes. An unconverged evaluation never counts
    as a converged solution.
    """
    _validate(gamma, epsilon, max_iterations)
    if evaluation_epsilon <= 0 or max_evaluation_iterations < 1:
        raise ValueError(
            "evaluation_epsilon and max_evaluation_iterations must be positive"
        )
    start = perf_counter()
    transitions = _prepare(mdp)
    values = dict.fromkeys(mdp.states, 0.0)
    policy = {s: next(iter(actions)) for s, actions in transitions.items()}
    history = []
    converged = False
    for iteration in range(1, max_iterations + 1):
        evaluation_converged = False
        for evaluation_steps in range(1, max_evaluation_iterations + 1):
            # TODO 4a: Evaluate the current policy with a synchronous
            # Bellman expectation update for every state.
            # Compute `updated` and the maximum value change `delta`.
            # Bellman expectation update for the current policy.
            updated = {
                s: _q(actions[policy[s]], values, gamma)
                for s, actions in transitions.items()
            }
            delta = max(abs(updated[s] - values[s]) for s in mdp.states)
            values = updated
            if delta < evaluation_epsilon:
                evaluation_converged = True
                break
        # TODO 4b: Improve the policy greedily with respect to `values`.
        # Store the new state-to-action mapping in `improved`.
        # Improve the policy greedily with respect to the evaluated values.
        improved = {
            s: _greedy(actions, values, gamma)
            for s, actions in transitions.items()
        }
        changes = sum(improved[s] != policy[s] for s in mdp.states)
        policy = improved
        record = {
            "iteration": iteration,
            "delta": delta,
            "policy_changes": changes,
            "evaluation_iterations": evaluation_steps,
            "evaluation_converged": evaluation_converged,
            "elapsed_seconds": perf_counter() - start,
        }
        history.append(record)
        if on_iteration:
            on_iteration(record.copy())
        if changes == 0 and evaluation_converged:
            converged = True
            break
        if not evaluation_converged:
            break
    return SolveResult(
        values, policy, history, converged, len(history), perf_counter() - start
    )
