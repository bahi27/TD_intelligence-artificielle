
import os
import random

from flask import Flask, jsonify, render_template, request, session

from game import (
    AI,
    HUMAN,
    create_board,
    get_valid_moves,
    get_winner,
    is_terminal,
    make_move,
)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("CONNECT4_SECRET_KEY", "connect4-local-classroom-only"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# ALGORITHM_MODULE = os.environ.get("CONNECT4_ALGORITHMS", "solution").lower()
# if ALGORITHM_MODULE not in {"solution", "student"}:
#     raise RuntimeError("CONNECT4_ALGORITHMS must be 'solution' or 'student'")
# algorithms = import_module(
#     "algorithms_sol" if ALGORITHM_MODULE == "solution" else "algorithms"
# )
import algorithms as algorithms


def game_state():
    board = session.get("board")
    if board is None:
        board = create_board()
        session["board"] = board
        session["turn"] = HUMAN
    return board


def snapshot(board):
    winner = get_winner(board)
    terminal = is_terminal(board)
    return {
        "board": board,
        "turn": None if terminal else session.get("turn", HUMAN),
        "winner": winner,
        "terminal": terminal,
        "draw": terminal and winner is None,
        "valid_moves": [] if terminal else get_valid_moves(board),
    }


def error(message, status=400):
    return jsonify({"error": message}), status


def integer_parameter(data, key, default, minimum, maximum):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def state():
    return jsonify(snapshot(game_state()))


@app.post("/api/new-game")
def new_game():
    session["board"] = create_board()
    session["turn"] = HUMAN
    return jsonify(snapshot(session["board"]))


@app.post("/api/play")
def play():
    board = game_state()
    if is_terminal(board):
        return error("Game is already over")
    if session.get("turn") != HUMAN:
        return error("It is not the human player's turn")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Expected a JSON object")
    column = data.get("column")
    if isinstance(column, bool) or not isinstance(column, int):
        return error("column must be an integer")
    if column not in get_valid_moves(board):
        return error("Illegal column")
    board = make_move(board, column, HUMAN)
    session["board"] = board
    session["turn"] = None if is_terminal(board) else AI
    return jsonify(snapshot(board))


@app.post("/api/ai-move")
def ai_move():
    board = game_state()
    if is_terminal(board):
        return error("Game is already over")
    if session.get("turn") != AI:
        return error("It is not the AI player's turn")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Expected a JSON object")

    algorithm = data.get("algorithm", "minimax")
    if algorithm not in {"random", "minimax", "alphabeta", "mcts"}:
        return error("Unknown algorithm")

    try:
        if algorithm == "random":
            move = random.choice(get_valid_moves(board))
            result = {
                "move": move,
                "score": None,
                "nodes_explored": 0,
                "time": 0.0,
                "search_tree": {"nodes": [], "truncated": False},
                "events": [],
            }
        elif algorithm == "mcts":
            simulations = integer_parameter(data, "num_simulations", 500, 1, 10000)
            result = algorithms.mcts(board, num_simulations=simulations)
        else:
            depth = integer_parameter(data, "depth", 4, 1, 7)
            result = getattr(algorithms, algorithm)(board, depth=depth)
    except (ValueError, TypeError) as exc:
        return error(str(exc))

    move = result.get("move")
    if move not in get_valid_moves(board):
        return error("Algorithm did not return a valid move. Check its TODOs.", 422)

    board = make_move(board, move, AI)
    session["board"] = board
    session["turn"] = None if is_terminal(board) else HUMAN
    return jsonify({"state": snapshot(board), "search": result})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
