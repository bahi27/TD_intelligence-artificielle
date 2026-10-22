"""Exercise 4 — Comparing Search Algorithms.

Benchmarks Minimax, Alpha-Beta Pruning, and MCTS on Connect Four.
"""

import matplotlib.pyplot as plt
from game import create_board
from algorithms import minimax, alphabeta, mcts


# ---------------------------------------------------------------------------
# 1. Benchmarking function
# ---------------------------------------------------------------------------

def benchmark(board, algorithm, **kwargs):
    """Execute *algorithm* on *board* and return a summary dictionary.

    Parameters
    ----------
    board : list[list[int]]
        Current Connect Four board state.
    algorithm : callable
        One of ``minimax``, ``alphabeta``, or ``mcts``.
    **kwargs
        Extra keyword arguments forwarded to the algorithm
        (e.g. ``depth=4`` or ``num_simulations=1000``).

    Returns
    -------
    dict
        Keys: name, move, score, nodes_explored, time.
    """
    result = algorithm(board, **kwargs)
    return {
        "name": algorithm.__name__,
        "move": result["move"],
        "score": result["score"],
        "nodes_explored": result["nodes_explored"],
        "time": result["time"],
    }


# ---------------------------------------------------------------------------
# 2 & 3 & 4. Automated experiments
# ---------------------------------------------------------------------------

def run_experiments():
    """Run all benchmark configurations and return the results table."""
    board = create_board()
    depths = [1, 2, 3, 4, 5]
    simulations = [100, 500, 1000, 2000]
    results = []

    # --- Minimax vs Alpha-Beta at various depths ---
    for d in depths:
        for algo in (minimax, alphabeta):
            r = benchmark(board, algo, depth=d)
            r["config"] = f"Depth {d}"
            results.append(r)

    # --- MCTS at various simulation budgets ---
    for n in simulations:
        r = benchmark(board, mcts, num_simulations=n, seed=42)
        r["config"] = f"{n} simulations"
        results.append(r)

    return results


def print_table(results):
    """Pretty-print results as a formatted table."""
    header = f"{'Algorithm':<12} {'Configuration':<20} {'Move':>4} {'Score':>12} {'Nodes':>8} {'Time (s)':>10}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in results:
        score_str = (
            f"{r['score']:.4f}" if isinstance(r["score"], float) else str(r["score"])
        )
        print(
            f"{r['name']:<12} {r['config']:<20} {r['move']:>4} "
            f"{score_str:>12} {r['nodes_explored']:>8} {r['time']:>10.6f}"
        )
    print(sep)


def verify_minimax_alphabeta(results):
    """Check that Minimax and Alpha-Beta agree on score and that AB ≤ MM nodes."""
    depths = sorted({r["config"] for r in results if r["name"] in ("minimax", "alphabeta")})
    all_ok = True
    for cfg in depths:
        mm = next(r for r in results if r["name"] == "minimax" and r["config"] == cfg)
        ab = next(r for r in results if r["name"] == "alphabeta" and r["config"] == cfg)
        same_score = mm["score"] == ab["score"]
        fewer_nodes = ab["nodes_explored"] <= mm["nodes_explored"]
        status = "OK" if (same_score and fewer_nodes) else "FAIL"
        if not (same_score and fewer_nodes):
            all_ok = False
        print(
            f"  {cfg}: score {'=' if same_score else '!='} "
            f"(MM={mm['score']}, AB={ab['score']}), "
            f"nodes AB({ab['nodes_explored']}) {'<=' if fewer_nodes else '>'} "
            f"MM({mm['nodes_explored']})  [{status}]"
        )
    print(f"  Verification: {'PASSED' if all_ok else 'FAILED'}")


# ---------------------------------------------------------------------------
# 5. Visualization
# ---------------------------------------------------------------------------

def plot_results(results):
    """Generate the two required plots and save them to disk."""

    # --- Plot 1: Nodes vs Depth for Minimax & Alpha-Beta ---
    mm_results = [r for r in results if r["name"] == "minimax"]
    ab_results = [r for r in results if r["name"] == "alphabeta"]

    mm_depths = [int(r["config"].split()[-1]) for r in mm_results]
    mm_nodes = [r["nodes_explored"] for r in mm_results]
    ab_depths = [int(r["config"].split()[-1]) for r in ab_results]
    ab_nodes = [r["nodes_explored"] for r in ab_results]

    fig1, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(mm_depths, mm_nodes, "o-", label="Minimax", linewidth=2)
    ax1.plot(ab_depths, ab_nodes, "s--", label="Alpha-Beta", linewidth=2)
    ax1.set_xlabel("Search Depth")
    ax1.set_ylabel("Nodes Explored")
    ax1.set_title("Nodes Explored vs Search Depth")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    fig1.tight_layout()
    fig1.savefig("nodes_vs_depth.png", dpi=150)
    print("  Saved: nodes_vs_depth.png")

    # --- Plot 2: Time vs Simulations for MCTS ---
    mcts_results = [r for r in results if r["name"] == "mcts"]
    mcts_sims = [int(r["config"].split()[0]) for r in mcts_results]
    mcts_times = [r["time"] for r in mcts_results]

    fig2, ax2 = plt.subplots(figsize=(8, 5))
    ax2.plot(mcts_sims, mcts_times, "D-", color="green", label="MCTS", linewidth=2)
    ax2.set_xlabel("Number of Simulations")
    ax2.set_ylabel("Execution Time (s)")
    ax2.set_title("MCTS Execution Time vs Number of Simulations")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    fig2.tight_layout()
    fig2.savefig("mcts_time_vs_simulations.png", dpi=150)
    print("  Saved: mcts_time_vs_simulations.png")

    plt.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n=== Running Benchmarks ===\n")
    results = run_experiments()

    print("\n=== Results Table ===\n")
    print_table(results)

    print("\n=== Verification: Minimax vs Alpha-Beta ===\n")
    verify_minimax_alphabeta(results)

    print("\n=== Generating Plots ===\n")
    plot_results(results)

    print("\nDone.")

