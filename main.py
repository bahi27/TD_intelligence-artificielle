"""Compare Dijkstra and A* on a difficult random Pokémon map."""

from pokemon_game import (
    draw_map,
    generate_hard_map,
    visualize_path,
)
from search import (
    a_star,
    dijkstra,
    generate_random_path,
    path_cost,
)

# Keep a fixed seed while developing and grading.
# Use None to obtain a different random map each time.
MAP_SEED = 1
RANDOM_PATH_SEED = 10


def main() -> None:
    """Generate one map and compare Dijkstra with A*."""
    game_map, start, goal = generate_hard_map(
        rows=20,
        columns=30,
        tree_probability=0.20,
        rock_probability=0.45,
        minimum_distance=30,
        seed=MAP_SEED,
    )

    print(f"Initial state: {start}")
    print(f"Goal state:    {goal}")

    # Display the generated environment.
    draw_map(
        game_map,
        start,
        goal,
    )

    # ---------------------------------------------------------------
    # Random valid path demonstration
    # ---------------------------------------------------------------

    random_path = generate_random_path(
        game_map,
        start,
        goal,
        seed=RANDOM_PATH_SEED,
    )

    random_path_cost = path_cost(
        game_map,
        random_path,
    )

    print("\nRandom valid path")
    print("-----------------")
    print(f"Path length: {len(random_path) - 1}")
    print(f"Path cost:   {random_path_cost}")
    print(f"Path:        {random_path}")

    random_animation = visualize_path(
        game_map,
        start,
        goal,
        random_path,
        interval=2,
        repeat=False,
    )

    _ = random_animation

    # ---------------------------------------------------------------
    # Dijkstra
    # ---------------------------------------------------------------

    dijkstra_path, dijkstra_considered = dijkstra(
        game_map,
        start,
        goal,
    )

    dijkstra_cost = path_cost(
        game_map,
        dijkstra_path,
    )

    print("\nDijkstra")
    print("---------")
    print(f"Path length:       {len(dijkstra_path) - 1}")
    print(f"Path cost:         {dijkstra_cost}")
    print(f"Considered states: {dijkstra_considered}")
    print(f"Path:              {dijkstra_path}")

    dijkstra_animation = visualize_path(
        game_map,
        start,
        goal,
        dijkstra_path,
        interval=2,
        repeat=False,
    )

    _ = dijkstra_animation

    # ---------------------------------------------------------------
    # A*
    # ---------------------------------------------------------------

    astar_path, astar_considered = a_star(
        game_map,
        start,
        goal,
    )

    astar_cost = path_cost(
        game_map,
        astar_path,
    )

    print("\nA*")
    print("--")
    print(f"Path length:       {len(astar_path) - 1}")
    print(f"Path cost:         {astar_cost}")
    print(f"Considered states: {astar_considered}")
    print(f"Path:              {astar_path}")

    astar_animation = visualize_path(
        game_map,
        start,
        goal,
        astar_path,
        interval=2,
        repeat=False,
    )

    _ = astar_animation

    # ---------------------------------------------------------------
    # Comparison
    # ---------------------------------------------------------------

    print("\nComparison")
    print("----------")
    print("Same optimal cost: " f"{dijkstra_cost == astar_cost}")

    print(
        "Difference in considered states: " f"{dijkstra_considered - astar_considered}"
    )


if __name__ == "__main__":
    main()
