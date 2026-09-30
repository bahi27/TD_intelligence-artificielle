"""Search algorithms for the Pokémon navigation exercise."""

from __future__ import annotations

import random
from collections import deque

from pokemon_game import GameMap, State, successors


def generate_random_path(
    game_map: GameMap,
    start: State,
    goal: State,
    seed: int | None = None,
    max_steps: int = 10000,
    max_attempts: int = 100,
) -> list[State]:
    """Generate a random valid path from the start to the goal.

    This function is provided only to demonstrate the path visualization.
    It is not a search algorithm and is not guaranteed to return a shortest
    path.

    At each step, the trainer randomly chooses one valid neighboring state.
    Unvisited neighbors are preferred, but previously visited states may be
    selected when necessary.

    Parameters
    ----------
    game_map : list[list[str]]
        The Pokémon map.
    start : tuple[int, int]
        Initial trainer position.
    goal : tuple[int, int]
        Pokémon Center position.
    seed : int or None, default=None
        Random seed used to make the generated path reproducible.
    max_steps : int, default=1000
        Maximum number of movements in one attempt.
    max_attempts : int, default=100
        Maximum number of random walks attempted.

    Returns
    -------
    list[tuple[int, int]]
        A valid path beginning at ``start`` and ending at ``goal``.

    Raises
    ------
    RuntimeError
        If no random path reaches the goal within the allowed attempts.
    """
    if start == goal:
        return [start]

    if max_steps < 1:
        raise ValueError("max_steps must be at least 1.")

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    rng = random.Random(seed)

    for _ in range(max_attempts):
        path = [start]
        visited = {start}
        current = start

        for _ in range(max_steps):
            neighboring_states = successors(game_map, current)

            if not neighboring_states:
                break

            unvisited_neighbors = [
                state for state in neighboring_states if state not in visited
            ]

            if unvisited_neighbors:
                next_state = rng.choice(unvisited_neighbors)
            else:
                next_state = rng.choice(neighboring_states)

            path.append(next_state)
            visited.add(next_state)
            current = next_state

            if current == goal:
                return path

    raise RuntimeError(
        "The random walk did not reach the goal. "
        "Try increasing max_steps or max_attempts, or use another seed."
    )


def _reconstruct_path(
    parents: dict[State, State | None],
    goal: State,
) -> list[State]:
    """Reconstruct a path from the parent dictionary."""
    path = []

    current = goal

    while current is not None:
        path.append(current)
        current = parents[current]

    path.reverse()

    return path


def breadth_first_search(
    game_map: GameMap,
    start: State,
    goal: State,
) -> list[State]:
    """Return a shortest path using Breadth-First Search."""

    path = [start]
    visited = {start}
    current = start
    parents={start:None}
    Q = deque()
    Q.append(start)
    while Q:
        current = Q.popleft()
        if current == goal :
            return _reconstruct_path(parents,goal)
        neighboring_states = successors(game_map, current)
        for state in neighboring_states:
            if state not in visited:
                visited.add(state)
                parents[state]= current
                Q.append(state)

    return []
    
    


def depth_first_search(
    game_map: GameMap,
    start: State,
    goal: State,
) -> list[State]:
    """Return a path using Depth-First Search."""
    ...
    visited={start}
    parents={start:None}
    path=[]
    stack =[start]
    while stack:
        current=stack.pop()
        if current == goal:
            return _reconstruct_path(parents,goal)
        neighboring_states = successors(game_map, current)
        for state in neighboring_states:
            if state not in visited:
                visited.add(state)
                parents[state]=current
                stack.append(state)
    return []
    