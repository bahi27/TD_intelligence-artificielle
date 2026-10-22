"""
Connect Four — Game Engine

This module contains the game rules and evaluation functions.
Students should not modify this file.

Board representation:
    0 = Empty cell
    1 = Human player
    2 = AI player

The board is a 6x7 list of lists.
Row 0 is the top row.
"""

ROWS = 6
COLS = 7
EMPTY = 0
HUMAN = 1
AI = 2

WIN_SCORE = 1_000_000


def create_board():
    """Create an empty Connect Four board."""
    return [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]


def get_valid_moves(board):
    """
    Return the list of columns where a disc can be dropped.
    """
    return [col for col in range(COLS) if board[0][col] == EMPTY]


def make_move(board, column, player):
    """
    Drop a disc into the selected column.

    Returns a NEW board without modifying the original.

    Raises ValueError if the move is invalid.
    """
    if column not in get_valid_moves(board):
        raise ValueError(f"Invalid move: column {column}")

    new_board = [row.copy() for row in board]

    for row in range(ROWS - 1, -1, -1):
        if new_board[row][column] == EMPTY:
            new_board[row][column] = player
            break

    return new_board


def check_winner(board, player):
    """
    Return True if the player has four consecutive discs
    horizontally, vertically, or diagonally.
    """

    # Horizontal
    for row in range(ROWS):
        for col in range(COLS - 3):
            if all(board[row][col + i] == player for i in range(4)):
                return True

    # Vertical
    for row in range(ROWS - 3):
        for col in range(COLS):
            if all(board[row + i][col] == player for i in range(4)):
                return True

    # Diagonal: top-left to bottom-right
    for row in range(ROWS - 3):
        for col in range(COLS - 3):
            if all(board[row + i][col + i] == player for i in range(4)):
                return True

    # Diagonal: bottom-left to top-right
    for row in range(3, ROWS):
        for col in range(COLS - 3):
            if all(board[row - i][col + i] == player for i in range(4)):
                return True

    return False


def is_terminal(board):
    """
    Return True if the game is over:
    - Human wins
    - AI wins
    - Board is full (draw)
    """
    return (
        check_winner(board, HUMAN)
        or check_winner(board, AI)
        or len(get_valid_moves(board)) == 0
    )


def get_winner(board):
    """
    Return:
        HUMAN if the human wins
        AI if the AI wins
        None if the game is a draw or not finished
    """
    if check_winner(board, HUMAN):
        return HUMAN

    if check_winner(board, AI):
        return AI

    return None


def evaluate_window(window, player):
    """
    Evaluate a group of four consecutive cells.

    Rewards:
        4 discs: +100
        3 discs + 1 empty: +5
        2 discs + 2 empty: +2

    Penalty:
        Opponent has 3 discs + 1 empty: -4
    """
    opponent = HUMAN if player == AI else AI

    score = 0

    player_count = window.count(player)
    opponent_count = window.count(opponent)
    empty_count = window.count(EMPTY)

    if player_count == 4:
        score += 100
    elif player_count == 3 and empty_count == 1:
        score += 5
    elif player_count == 2 and empty_count == 2:
        score += 2

    if opponent_count == 3 and empty_count == 1:
        score -= 4

    return score


def evaluate_board(board, player=AI):
    """
    Heuristic evaluation of a non-terminal board.

    A positive score favors the given player.
    A negative score favors the opponent.

    Terminal states receive a large positive/negative score.
    """

    opponent = HUMAN if player == AI else AI

    # Terminal states
    if check_winner(board, player):
        return WIN_SCORE

    if check_winner(board, opponent):
        return -WIN_SCORE

    if len(get_valid_moves(board)) == 0:
        return 0

    score = 0

    # Prefer controlling the center column
    center_col = COLS // 2
    center_count = sum(board[row][center_col] == player for row in range(ROWS))
    score += center_count * 3

    # Horizontal windows
    for row in range(ROWS):
        for col in range(COLS - 3):
            window = board[row][col : col + 4]
            score += evaluate_window(window, player)

    # Vertical windows
    for col in range(COLS):
        for row in range(ROWS - 3):
            window = [board[row + i][col] for i in range(4)]
            score += evaluate_window(window, player)

    # Diagonal windows: top-left to bottom-right
    for row in range(ROWS - 3):
        for col in range(COLS - 3):
            window = [board[row + i][col + i] for i in range(4)]
            score += evaluate_window(window, player)

    # Diagonal windows: bottom-left to top-right
    for row in range(3, ROWS):
        for col in range(COLS - 3):
            window = [board[row - i][col + i] for i in range(4)]
            score += evaluate_window(window, player)

    return score
