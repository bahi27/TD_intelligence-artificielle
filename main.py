"""Run the Pokémon search exercise."""

import matplotlib

matplotlib.use("TkAgg")

from pokemon_game import (
    draw_map,
    generate_map,
    path_to_actions,
    visualize_path,
)
from search import generate_random_path, breadth_first_search, depth_first_search

# Using a fixed seed gives every student the same example.
# Replace it with None to generate a different map on each execution.
MAP_SEED = None
PATH_SEED = 10


def main() -> None:
    """Generate a map and demonstrate the path visualization."""
    game_map, start, goal = generate_map(
        rows=10,
        columns=14,
        tree_probability=0.25,
        seed=MAP_SEED,
    )

    print(f"Initial state: {start}")
    print(f"Goal state:    {goal}")

    # First display the randomly generated initial map.
    # Close this window to continue to the animation.
    draw_map(
        game_map,
        start,
        goal,
    )

    # Generate a random valid example path.
    random_path = generate_random_path(
        game_map,
        start,
        goal,
        seed=PATH_SEED,
    )

    print("\nRandom example path:")
    print(random_path)

    print("\nCorresponding actions:")
    print(path_to_actions(random_path))

    print(f"\nPath cost: {len(random_path) - 1}")

    # Animate the trainer walking along the generated path.
    animation = visualize_path(
        game_map,
        start,
        goal,
        random_path,
        interval=300,
        repeat=False,
    )

    # Keep a reference to the animation until the window is closed.
    _ = animation

    bfs_path = breadth_first_search(game_map, start, goal)

    print("\nBFS example path:")
    print(bfs_path)

    print("\nCorresponding actions:")
    print(path_to_actions(bfs_path))

    print(f"\nPath cost: {len(bfs_path) - 1}")

    animation = visualize_path(game_map, start, goal, bfs_path)
    _ = animation

    dfs_path = depth_first_search(game_map, start, goal)

    print("\nDFS example path:")
    print(dfs_path)

    print("\nCorresponding actions:")
    print(path_to_actions(dfs_path))

    print(f"\nPath cost: {len(dfs_path) - 1}")

    animation = visualize_path(game_map, start, goal, dfs_path)
    _ = animation


if __name__ == "__main__":
    main()
