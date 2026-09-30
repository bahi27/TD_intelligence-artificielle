"""Utilities for the Pokémon search exercise.

This module provides:

- random solvable map generation;
- successor generation;
- path validation;
- static map visualization;
- animated visualization of the trainer following a path.

Students should not modify this file. They only implement BFS and DFS in
``search.py``.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Sequence

import cairosvg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image

State = tuple[int, int]
GameMap = list[list[str]]


# ---------------------------------------------------------------------------
# Map symbols
# ---------------------------------------------------------------------------

TREE = "T"
GRASS = "G"

ACTION_ORDER = ("up", "right", "down", "left")

ACTION_DELTAS: dict[str, State] = {
    "up": (-1, 0),
    "right": (0, 1),
    "down": (1, 0),
    "left": (0, -1),
}


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

SPRITE_DIRECTORY = Path("./pokemon-sprites")

SPRITE_PATHS = {
    "tree": SPRITE_DIRECTORY / "tree.svg",
    "grass": SPRITE_DIRECTORY / "grass.svg",
    "trainer": SPRITE_DIRECTORY / "trainer.svg",
    "clinic": SPRITE_DIRECTORY / "clinic.svg",
}


# ---------------------------------------------------------------------------
# Map generation
# ---------------------------------------------------------------------------


def generate_map(
    rows: int = 10,
    columns: int = 14,
    tree_probability: float = 0.25,
    seed: int | None = None,
) -> tuple[GameMap, State, State]:
    """Generate a random map with a reachable start and goal.

    The outside border always consists of trees. Interior cells are generated
    randomly as grass or trees. Maps are regenerated until the selected start
    and goal positions are connected.

    Parameters
    ----------
    rows : int, default=10
        Total number of map rows, including the tree border.
    columns : int, default=14
        Total number of map columns, including the tree border.
    tree_probability : float, default=0.25
        Probability that an interior cell contains a tree.
    seed : int or None, default=None
        Random seed. Supplying a seed makes the generated map reproducible.

    Returns
    -------
    game_map : list[list[str]]
        The generated map.
    start : tuple[int, int]
        Initial trainer position.
    goal : tuple[int, int]
        Pokémon Center position.

    Raises
    ------
    ValueError
        If the map dimensions or tree probability are invalid.
    RuntimeError
        If a solvable map cannot be generated after many attempts.
    """
    if rows < 5 or columns < 5:
        raise ValueError("The map must contain at least 5 rows and 5 columns.")

    if not 0.0 <= tree_probability < 1.0:
        raise ValueError("tree_probability must be in the interval [0, 1).")

    rng = np.random.default_rng(seed)

    maximum_attempts = 1_000

    for _ in range(maximum_attempts):
        game_map: GameMap = []

        for row in range(rows):
            map_row: list[str] = []

            for column in range(columns):
                is_border = (
                    row == 0 or row == rows - 1 or column == 0 or column == columns - 1
                )

                if is_border:
                    map_row.append(TREE)
                else:
                    symbol = TREE if rng.random() < tree_probability else GRASS
                    map_row.append(symbol)

            game_map.append(map_row)

        grass_cells = [
            (row, column)
            for row in range(1, rows - 1)
            for column in range(1, columns - 1)
            if game_map[row][column] == GRASS
        ]

        if len(grass_cells) < 2:
            continue

        start_index, goal_index = rng.choice(
            len(grass_cells),
            size=2,
            replace=False,
        )

        start = grass_cells[int(start_index)]
        goal = grass_cells[int(goal_index)]

        if _is_reachable(game_map, start, goal):
            return game_map, start, goal

    raise RuntimeError(
        "Could not generate a solvable map. " "Try reducing tree_probability."
    )


def _is_reachable(
    game_map: GameMap,
    start: State,
    goal: State,
) -> bool:
    """Return whether the goal can be reached from the start.

    This private function is used only to validate randomly generated maps.
    It is deliberately not exposed as a solution to the student exercise.
    """
    frontier = [start]
    visited = {start}

    while frontier:
        current = frontier.pop(0)

        if current == goal:
            return True

        for next_state in successors(game_map, current):
            if next_state not in visited:
                visited.add(next_state)
                frontier.append(next_state)

    return False


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


def is_valid_state(
    game_map: GameMap,
    state: State,
) -> bool:
    """Return whether a state is inside the map and not occupied by a tree."""
    row, column = state

    if row < 0 or column < 0:
        return False

    if row >= len(game_map):
        return False

    if column >= len(game_map[0]):
        return False

    return game_map[row][column] != TREE


def transition(
    game_map: GameMap,
    state: State,
    action: str,
) -> State:
    """Apply an action and return the resulting state.

    If the action would move the trainer into a tree or outside the map, the
    original state is returned.

    Parameters
    ----------
    game_map : list[list[str]]
        Pokémon map.
    state : tuple[int, int]
        Current trainer position.
    action : str
        One of ``"up"``, ``"right"``, ``"down"``, or ``"left"``.

    Returns
    -------
    tuple[int, int]
        Resulting state.
    """
    if action not in ACTION_DELTAS:
        raise ValueError(
            f"Unknown action {action!r}. " f"Expected one of {ACTION_ORDER}."
        )

    row_change, column_change = ACTION_DELTAS[action]

    next_state = (
        state[0] + row_change,
        state[1] + column_change,
    )

    if is_valid_state(game_map, next_state):
        return next_state

    return state


def valid_actions(
    game_map: GameMap,
    state: State,
) -> list[str]:
    """Return valid actions in the required priority order."""
    actions: list[str] = []

    for action in ACTION_ORDER:
        if transition(game_map, state, action) != state:
            actions.append(action)

    return actions


def successors(
    game_map: GameMap,
    state: State,
) -> list[State]:
    """Return valid successor states.

    Successors are returned in the following order:

    ``up, right, down, left``.
    """
    return [
        transition(game_map, state, action) for action in valid_actions(game_map, state)
    ]


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def validate_path(
    game_map: GameMap,
    path: Sequence[State],
    start: State | None = None,
    goal: State | None = None,
) -> None:
    """Validate a path.

    Parameters
    ----------
    game_map : list[list[str]]
        Pokémon map.
    path : sequence of tuple[int, int]
        Sequence of visited states.
    start : tuple[int, int] or None, default=None
        Expected first state.
    goal : tuple[int, int] or None, default=None
        Expected final state.

    Raises
    ------
    ValueError
        If the path is empty, crosses a tree, jumps between cells, or does not
        begin/end at the expected states.
    """
    if not path:
        raise ValueError("The path is empty.")

    if start is not None and path[0] != start:
        raise ValueError(
            f"The path starts at {path[0]}, but the expected start is {start}."
        )

    if goal is not None and path[-1] != goal:
        raise ValueError(
            f"The path ends at {path[-1]}, but the expected goal is {goal}."
        )

    for state in path:
        if not is_valid_state(game_map, state):
            raise ValueError(f"The path contains the invalid state {state}.")

    for current, next_state in zip(path, path[1:]):
        row_distance = abs(current[0] - next_state[0])
        column_distance = abs(current[1] - next_state[1])

        if row_distance + column_distance != 1:
            raise ValueError(
                f"Invalid movement from {current} to {next_state}. "
                "Consecutive states must be adjacent."
            )


def path_to_actions(path: Sequence[State]) -> list[str]:
    """Convert a valid state path into its corresponding action sequence."""
    if len(path) < 2:
        return []

    reverse_deltas = {delta: action for action, delta in ACTION_DELTAS.items()}

    actions: list[str] = []

    for current, next_state in zip(path, path[1:]):
        delta = (
            next_state[0] - current[0],
            next_state[1] - current[1],
        )

        if delta not in reverse_deltas:
            raise ValueError(f"Invalid movement from {current} to {next_state}.")

        actions.append(reverse_deltas[delta])

    return actions


# ---------------------------------------------------------------------------
# Sprite loading
# ---------------------------------------------------------------------------


def _load_svg(
    path: Path,
    size: int = 256,
) -> np.ndarray:
    """Load an SVG sprite as an RGBA NumPy array."""
    if not path.exists():
        raise FileNotFoundError(f"Sprite file not found: {path}")

    png_data = cairosvg.svg2png(
        url=str(path),
        output_width=size,
        output_height=size,
    )

    image = Image.open(BytesIO(png_data)).convert("RGBA")
    return np.asarray(image)


def load_sprites() -> dict[str, np.ndarray]:
    """Load all sprites required by the game."""
    return {name: _load_svg(path) for name, path in SPRITE_PATHS.items()}


# ---------------------------------------------------------------------------
# Visualization helpers
# ---------------------------------------------------------------------------


def _add_sprite(
    axes: plt.Axes,
    sprite: np.ndarray,
    state: State,
    zoom: float,
    zorder: int,
) -> AnnotationBbox:
    """Place a sprite at a map position."""
    row, column = state

    image = OffsetImage(sprite, zoom=zoom)

    box = AnnotationBbox(
        image,
        (column + 0.5, row + 0.5),
        frameon=False,
        box_alignment=(0.5, 0.5),
        zorder=zorder,
    )

    axes.add_artist(box)
    return box


def _prepare_axes(
    game_map: GameMap,
) -> tuple[plt.Figure, plt.Axes]:
    """Create axes configured for displaying the map."""
    rows = len(game_map)
    columns = len(game_map[0])

    figure, axes = plt.subplots(
        figsize=(columns, rows),
    )

    axes.set_xlim(0, columns)
    axes.set_ylim(rows, 0)
    axes.set_aspect("equal")

    axes.set_xticks([])
    axes.set_yticks([])

    for spine in axes.spines.values():
        spine.set_visible(False)

    return figure, axes


def _draw_background(
    axes: plt.Axes,
    game_map: GameMap,
    sprites: dict[str, np.ndarray],
    goal: State,
) -> None:
    """Draw all grass, trees, and the Pokémon Center."""
    rows = len(game_map)
    columns = len(game_map[0])

    for row in range(rows):
        for column in range(columns):
            state = (row, column)
            symbol = game_map[row][column]

            if symbol == TREE:
                _add_sprite(
                    axes,
                    sprites["tree"],
                    state,
                    zoom=0.22,
                    zorder=2,
                )
            else:
                _add_sprite(
                    axes,
                    sprites["grass"],
                    state,
                    zoom=0.22,
                    zorder=1,
                )

    _add_sprite(
        axes,
        sprites["clinic"],
        goal,
        zoom=0.21,
        zorder=3,
    )

    for row in range(rows + 1):
        axes.plot(
            [0, columns],
            [row, row],
            linewidth=0.4,
            alpha=0.25,
            zorder=0,
        )

    for column in range(columns + 1):
        axes.plot(
            [column, column],
            [0, rows],
            linewidth=0.4,
            alpha=0.25,
            zorder=0,
        )


# ---------------------------------------------------------------------------
# Public visualizations
# ---------------------------------------------------------------------------


def draw_map(
    game_map: GameMap,
    start: State,
    goal: State,
    show: bool = True,
) -> tuple[plt.Figure, plt.Axes]:
    """Display the initial map.

    Parameters
    ----------
    game_map : list[list[str]]
        Pokémon map.
    start : tuple[int, int]
        Trainer's initial state.
    goal : tuple[int, int]
        Pokémon Center position.
    show : bool, default=True
        Whether to immediately display the figure.

    Returns
    -------
    figure, axes
        Matplotlib figure and axes.
    """
    if not is_valid_state(game_map, start):
        raise ValueError(f"Invalid start state: {start}.")

    if not is_valid_state(game_map, goal):
        raise ValueError(f"Invalid goal state: {goal}.")

    sprites = load_sprites()
    figure, axes = _prepare_axes(game_map)

    _draw_background(
        axes,
        game_map,
        sprites,
        goal,
    )

    _add_sprite(
        axes,
        sprites["trainer"],
        start,
        zoom=0.20,
        zorder=4,
    )

    axes.set_title(
        f"Start: {start}    Goal: {goal}",
        pad=12,
    )

    figure.tight_layout()

    if show:
        plt.show()

    return figure, axes


def visualize_path(
    game_map: GameMap,
    start: State,
    goal: State,
    path: Sequence[State],
    interval: int = 500,
    repeat: bool = False,
) -> FuncAnimation:
    """Animate the trainer following a path.

    The supplied path is validated before the animation begins.

    Parameters
    ----------
    game_map : list[list[str]]
        Pokémon map.
    start : tuple[int, int]
        Expected initial state.
    goal : tuple[int, int]
        Expected final state.
    path : sequence of tuple[int, int]
        Path returned by a search algorithm.
    interval : int, default=500
        Delay between frames in milliseconds.
    repeat : bool, default=False
        Whether the animation should restart after reaching the goal.

    Returns
    -------
    matplotlib.animation.FuncAnimation
        Animation object.

    Notes
    -----
    Store the returned animation in a variable until ``plt.show()`` finishes.
    Otherwise, Python may garbage-collect it before it is displayed.
    """
    validate_path(
        game_map,
        path,
        start=start,
        goal=goal,
    )

    sprites = load_sprites()
    figure, axes = _prepare_axes(game_map)

    _draw_background(
        axes,
        game_map,
        sprites,
        goal,
    )

    trainer_box = _add_sprite(
        axes,
        sprites["trainer"],
        path[0],
        zoom=0.20,
        zorder=5,
    )

    visited_x: list[float] = []
    visited_y: list[float] = []

    (path_line,) = axes.plot(
        [],
        [],
        linewidth=2.5,
        linestyle="--",
        alpha=0.75,
        zorder=4,
    )

    status_text = axes.set_title(
        f"Step 0/{len(path) - 1}",
        pad=12,
    )

    def update(frame_index: int):
        state = path[frame_index]
        row, column = state

        trainer_box.xybox = (
            column + 0.5,
            row + 0.5,
        )
        trainer_box.xy = (
            column + 0.5,
            row + 0.5,
        )

        visited_x.append(column + 0.5)
        visited_y.append(row + 0.5)

        path_line.set_data(
            visited_x,
            visited_y,
        )

        status_text.set_text(f"Step {frame_index}/{len(path) - 1} — state {state}")

        return trainer_box, path_line, status_text

    animation = FuncAnimation(
        figure,
        update,
        frames=len(path),
        interval=interval,
        repeat=repeat,
        blit=False,
    )

    figure.tight_layout()
    plt.show()

    return animation


# ---------------------------------------------------------------------------
# Text representation
# ---------------------------------------------------------------------------


def print_map(
    game_map: GameMap,
    start: State,
    goal: State,
    trainer_state: State | None = None,
) -> None:
    """Print a simple text representation of the map."""
    current_trainer_state = start if trainer_state is None else trainer_state

    for row_index, map_row in enumerate(game_map):
        symbols: list[str] = []

        for column_index, symbol in enumerate(map_row):
            state = (row_index, column_index)

            if state == current_trainer_state:
                symbols.append("S")
            elif state == goal:
                symbols.append("C")
            else:
                symbols.append(symbol)

        print("".join(symbols))
