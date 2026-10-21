"""Cost-based search algorithms for the Pokémon environment."""

from __future__ import annotations

import heapq
import random
from itertools import count

from pokemon_game import (
    GameMap,
    State,
    movement_cost,
    successors,
)


def reconstruct_path(
    parents: dict[State, State | None],
    goal: State,
) -> list[State]:
    """Reconstruct a path from a parent dictionary."""
    path: list[State] = []
    current: State | None = goal

    while current is not None:
        path.append(current)
        current = parents[current]

    path.reverse()
    return path


def path_cost(
    game_map: GameMap,
    path: list[State],
) -> int:
    """Return the total cost of a path."""
    return sum(
        movement_cost(game_map, state)
        for state in path[1:]
    )


def manhattan_distance(
    state: State,
    goal: State,
) -> int:
    """Return the Manhattan distance between two states."""
    return (
        abs(state[0] - goal[0])
        + abs(state[1] - goal[1])
    )


def generate_random_path(
    game_map: GameMap,
    start: State,
    goal: State,
    seed: int | None = None,
) -> list[State]:
    """Generate a random valid path from start to goal.

    This function is provided only to demonstrate the visualization.
    It is not guaranteed to return a minimum-cost or shortest path.

    The function performs a randomized depth-first exploration: the valid
    successor states are shuffled before being added to the frontier.

    Parameters
    ----------
    game_map : GameMap
        Weighted Pokémon map.
    start : State
        Initial trainer position.
    goal : State
        Pokémon Center position.
    seed : int or None, default=None
        Random seed used to make the result reproducible.

    Returns
    -------
    list[State]
        A valid path beginning at ``start`` and ending at ``goal``.

    Raises
    ------
    RuntimeError
        If no path exists between the start and the goal.
    """
    rng = random.Random(seed)

    frontier = [start]

    parents: dict[State, State | None] = {
        start: None,
    }

    while frontier:
        current = frontier.pop()

        if current == goal:
            return reconstruct_path(parents, goal)

        next_states = successors(game_map, current)
        rng.shuffle(next_states)

        for next_state in next_states:
            if next_state in parents:
                continue

            parents[next_state] = current
            frontier.append(next_state)

    raise RuntimeError(
        "No path exists between the start and the goal."
    )

def dijkstra(
    game_map: GameMap,
    start: State,
    goal: State,
) -> tuple[list[State], int]:
    """Return a minimum-cost path using Dijkstra's algorithm.

    Returns
    -------
    path : list[State]
        Minimum-cost path from start to goal.
    considered_states : int
        Number of states removed from the priority queue.
    """
    frontier = []
    parent={start:None}
    g_cost={start:0}
    close = set()

    counter = count()
    f = 0
    consideredState =0
    heapq.heappush(frontier, (f, next(counter), start))
    while frontier:
        
        _, _, node = heapq.heappop(frontier)
        if node in close:
            continue  
        
        close.add(node)
        consideredState +=1
        if goal == node:
            return (reconstruct_path(parent,goal),consideredState)
        for s in successors(game_map, node):
            new_g = g_cost[node] + movement_cost(game_map, s)

            if s not in g_cost or new_g < g_cost[s]:  # s est nouveau OU new_g est meilleur que g_cost[s]
                g_cost[s] = new_g
                parent[s] = node
                f = new_g 
                heapq.heappush(frontier, (f,next(counter), s))
    raise RuntimeError("No path exist between start end goal    ")
    


def a_star(
    game_map: GameMap,
    start: State,
    goal: State,
) -> tuple[list[State], int]:
    """Return a minimum-cost path using A* search.

    The Manhattan distance is used as the heuristic.

    Returns
    -------
    path : list[State]
        Minimum-cost path from start to goal.
    considered_states : int
        Number of states removed from the priority queue.
    """
    ...
    frontier = []
    parent={start:None}
    g_cost={start:0}
    close = set()

    counter = count()
    f = manhattan_distance(start,goal)
    consideredState =0
    heapq.heappush(frontier, (f, next(counter), start))
    while frontier:
        
        _, _, node = heapq.heappop(frontier)
        if node in close:
            continue  
        
        close.add(node)
        consideredState +=1
        if goal == node:
            return (reconstruct_path(parent,goal),consideredState)
        for s in successors(game_map, node):
            new_g = g_cost[node] + movement_cost(game_map, s)

            if s not in g_cost or new_g < g_cost[s]:  # s est nouveau OU new_g est meilleur que g_cost[s]
                g_cost[s] = new_g
                parent[s] = node
                f = new_g + manhattan_distance(s, goal)
                heapq.heappush(frontier, (f,next(counter), s))
    raise RuntimeError("No path exist between start end goal")
