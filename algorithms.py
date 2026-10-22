"""Connect Four TD — student search algorithms.

Complete the TODO sections only. The game rules, tracing infrastructure,
and public function interfaces are provided.
"""

import math
import random
import time
from dataclasses import dataclass, field

from game import (
    AI, HUMAN, WIN_SCORE, check_winner, evaluate_board,
    get_valid_moves, get_winner, is_terminal, make_move,
)

MAX_VIS_NODES = 350
MAX_EVENTS = 1200


def _other(player):
    return HUMAN if player == AI else AI


class Trace:
    def __init__(self):
        self.nodes = {}
        self.events = []
        self.next_id = 0

    def node(self, parent, move, player, depth):
        if len(self.nodes) >= MAX_VIS_NODES:
            return None
        node_id = self.next_id
        self.next_id += 1
        self.nodes[node_id] = {
            "id": node_id, "parent": parent, "move": move,
            "player": player, "depth": depth, "score": None,
            "visits": 0, "mean_reward": None, "pruned": False,
            "alpha": None, "beta": None,
        }
        self.event("visit", node_id)
        return node_id

    def update(self, node_id, **kwargs):
        if node_id is None:
            return
        self.nodes[node_id].update(kwargs)
        self.event("update", node_id, **kwargs)

    def event(self, kind, node_id=None, **kwargs):
        if len(self.events) < MAX_EVENTS:
            self.events.append({"type": kind, "node": node_id, **kwargs})

    def result(self):
        return {"nodes": list(self.nodes.values()), "truncated": len(self.nodes) >= MAX_VIS_NODES}


def _final(move, score, explored, start, trace):
    return {
        "move": move,
        "score": score,
        "nodes_explored": explored,
        "time": round(time.perf_counter() - start, 6),
        "search_tree": trace.result(),
        "events": trace.events,
    }


def _validate(board, depth=None):
    if is_terminal(board):
        return False
    if depth is not None and (not isinstance(depth, int) or depth < 1):
        raise ValueError("depth must be a positive integer")
    return True


def minimax(board, depth=4):
    """Depth-limited Minimax. The AI (player 2) is always MAX."""
    start = time.perf_counter()
    trace = Trace()
    if not _validate(board, depth):
        return _final(None, evaluate_board(board, AI), 0, start, trace)

    explored = 0

    def search(state, remaining, player, parent=None, move=None, level=0):
        nonlocal explored
        explored += 1
        node_id = trace.node(parent, move, player, level)
        if remaining == 0 or is_terminal(state):
            score = evaluate_board(state, AI)
            trace.update(node_id, score=score)
            return score, None

        # TODO 1 (Minimax): Determine whether this is a MAX or MIN node.
        maximizing = player == AI


        # TODO 2: Initialize the best score and best move.
        best_score = -math.inf if maximizing else math.inf
        best_move = None

        for column in get_valid_moves(state):
            # TODO 3: Apply the move and recursively evaluate the child.
            child =make_move(state, column, player)
            value, _ = search(child,remaining-1 , _other(player),node_id, column, level +1)

            # TODO 4: Keep the best value and corresponding move.
            if(maximizing and value > best_score) or (not maximizing and value < best_score):
                best_score, best_move = value, column

        trace.update(node_id, score=best_score)
        return best_score, best_move

    score, move = search(board, depth, AI)
    return _final(move, score, explored, start, trace)


def alphabeta(board, depth=6):
    """Depth-limited Minimax with alpha-beta pruning (same move ordering)."""
    start = time.perf_counter()
    trace = Trace()
    if not _validate(board, depth):
        return _final(None, evaluate_board(board, AI), 0, start, trace)

    explored = 0

    def search(state, remaining, alpha, beta, player, parent=None, move=None, level=0):
        nonlocal explored
        explored += 1
        node_id = trace.node(parent, move, player, level)
        trace.update(node_id, alpha=alpha if math.isfinite(alpha) else None,
                     beta=beta if math.isfinite(beta) else None)
        if remaining == 0 or is_terminal(state):
            score = evaluate_board(state, AI)
            trace.update(node_id, score=score)
            return score, None

        maximizing = player == AI
        best_score = -math.inf if maximizing else math.inf
        best_move = None
        moves = get_valid_moves(state)
        for index, column in enumerate(moves):
            child = make_move(state, column, player)
            value, _ = search(child, remaining - 1, alpha, beta, _other(player), node_id, column, level + 1)
            if (maximizing and value > best_score) or (not maximizing and value < best_score):
                best_score, best_move = value, column
            # TODO 5 (Alpha-Beta): Update the appropriate bound.
            if maximizing:
                alpha = max(alpha, best_score)
            else:
                beta = min(beta, best_score)
            trace.update(node_id, score=best_score,
                         alpha=alpha if math.isfinite(alpha) else None,
                         beta=beta if math.isfinite(beta) else None)

            # TODO 6: Apply the pruning condition.
            if alpha >= beta:
                skipped = moves[index + 1:]
                if skipped:
                    trace.event("prune", node_id, skipped_moves=skipped,
                                alpha=alpha, beta=beta)
                    trace.update(node_id, pruned=True)
                break
        return best_score, best_move

    score, move = search(board, depth, -math.inf, math.inf, AI)
    return _final(move, score, explored, start, trace)


@dataclass
class MCTSNode:     
    board: list
    player_to_move: int
    parent: object = None
    move: int = None
    trace_id: int = None
    children: list = field(default_factory=list)
    visits: int = 0
    total_reward: float = 0.0
    untried_moves: list = field(default_factory=list)

    def __post_init__(self):
        self.untried_moves = [] if is_terminal(self.board) else get_valid_moves(self.board)

    def mean_for(self, player):
        """Rewards are stored from the perspective of the player who just moved."""
        return self.total_reward / self.visits if self.visits else 0.0


def mcts(board, num_simulations=1000, exploration=math.sqrt(2), seed=None):
    """UCT search with terminal random rollouts; AI is the root player.

    Each node stores rewards from the perspective of its *parent mover*.
    Thus UCT maximization is valid at both AI and HUMAN turns.
    Reward: win=1, draw=0.5, loss=0.
    """
    start = time.perf_counter()
    trace = Trace()
    if not _validate(board):
        return _final(None, None, 0, start, trace)
    if not isinstance(num_simulations, int) or num_simulations < 1:
        raise ValueError("num_simulations must be a positive integer")
    if exploration < 0:
        raise ValueError("exploration must be nonnegative")

    rng = random.Random(seed)
    root = MCTSNode(board=board, player_to_move=AI)
    root.trace_id = trace.node(None, None, AI, 0)
    created = 1

    for iteration in range(num_simulations):
        node = root
        # 1. Selection: traverse fully expanded, nonterminal nodes.
        while not node.untried_moves and node.children and not is_terminal(node.board):
            log_parent = math.log(node.visits)
            # TODO 7 (MCTS): Select the child maximizing UCT.
            # UCT = mean_reward + exploration * sqrt(log(parent_visits) / child_visits)
            # Each child's rewards are from the perspective of the player
            # who moved into that child.
            node = max(
                node.children,
                key=lambda child: (child.total_reward / child.visits)
                    + exploration * math.sqrt(log_parent / child.visits),
            )
            trace.event("select", node.trace_id, iteration=iteration)

        # 2. Expansion: add exactly one untried child.
        if node.untried_moves and not is_terminal(node.board):
            column = rng.choice(node.untried_moves)
            node.untried_moves.remove(column)
            next_board = make_move(node.board, column, node.player_to_move)
            child = MCTSNode(next_board, _other(node.player_to_move), node, column)
            child.trace_id = trace.node(node.trace_id, column, child.player_to_move,
                                        0 if node.trace_id is None else
                                        trace.nodes[node.trace_id]["depth"] + 1)
            node.children.append(child)
            node = child
            created += 1
            trace.event("expand", node.trace_id, iteration=iteration, move=column)

        # 3. Simulation: uniformly random play until terminal.
        rollout_board = node.board
        rollout_player = node.player_to_move
        while not is_terminal(rollout_board):
            column = rng.choice(get_valid_moves(rollout_board))
            rollout_board = make_move(rollout_board, column, rollout_player)
            rollout_player = _other(rollout_player)
        winner = get_winner(rollout_board)
        trace.event("simulation", node.trace_id, iteration=iteration, winner=winner)

        # 4. Backpropagation: reward for the player who moved into each node.
        while node is not None:
            # TODO 8: Increment the visit count and accumulate reward.
            # A win earns 1, a draw 0.5, and a loss 0.
            # Evaluate from the perspective of the player who entered this node.
            node.visits += 1
            previous_player = _other(node.player_to_move)
            reward = 1.0 if winner == previous_player else (0.5 if winner is None else 0.0)
            node.total_reward += reward
            trace.update(node.trace_id, visits=node.visits,
                         mean_reward=round(node.total_reward / node.visits, 4))
            node = node.parent

    # Most visited root child, with estimated AI win/draw reward.
    best = max(root.children, key=lambda child: child.visits)
    score = best.total_reward / best.visits
    return _final(best.move, round(score, 4), created, start, trace)
