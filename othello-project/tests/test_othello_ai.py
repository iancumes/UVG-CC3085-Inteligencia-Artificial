from __future__ import annotations

import random
import time

from client.othello_ai import (
    BLACK,
    EMPTY,
    WHITE,
    OthelloAI,
    apply_move,
    create_initial_board,
    legal_moves,
    next_turn_color,
)


def test_ai_rules_match_initial_othello_position() -> None:
    board = create_initial_board()

    assert legal_moves(board, BLACK) == ["d3", "c4", "f5", "e6"]
    assert legal_moves(board, WHITE) == ["e3", "f4", "c5", "d6"]


def test_ai_apply_move_flips_all_captured_discs() -> None:
    board = create_initial_board()
    updated = apply_move(board, "d3", BLACK)

    assert updated[2][3] == BLACK
    assert updated[3][3] == BLACK
    assert updated[3][4] == BLACK


def test_ai_returns_pass_only_when_no_legal_moves_are_available() -> None:
    ai = OthelloAI(move_budget_seconds=0.01, max_depth=2)

    assert ai.choose_move(create_initial_board(), WHITE, []) == "pass"


def test_ai_never_returns_move_outside_server_legal_moves() -> None:
    ai = OthelloAI(move_budget_seconds=0.05, max_depth=3)
    board = create_initial_board()
    moves = legal_moves(board, BLACK)

    assert ai.choose_move(board, BLACK, moves) in moves


def test_ai_prioritizes_available_corner() -> None:
    board = [[EMPTY for _ in range(8)] for _ in range(8)]
    board[0][1] = WHITE
    board[0][2] = BLACK
    board[1][0] = WHITE
    board[2][0] = BLACK
    ai = OthelloAI(move_budget_seconds=0.05, max_depth=3)
    moves = legal_moves(board, BLACK)

    assert "a1" in moves
    assert ai.choose_move(board, BLACK, moves) == "a1"


def test_ai_respects_small_time_budget() -> None:
    ai = OthelloAI(move_budget_seconds=0.005, max_depth=8)
    board = create_initial_board()
    moves = legal_moves(board, BLACK)

    start = time.perf_counter()
    move = ai.choose_move(board, BLACK, moves)
    elapsed = time.perf_counter() - start

    assert move in moves
    assert elapsed < 0.2


def test_ai_vs_random_game_has_no_invalid_moves() -> None:
    ai = OthelloAI(move_budget_seconds=0.01, max_depth=2)
    rng = random.Random(3085)
    board = create_initial_board()
    color = BLACK

    for _ in range(128):
        moves = legal_moves(board, color)
        if not moves:
            other = WHITE if color == BLACK else BLACK
            if not legal_moves(board, other):
                break
            color = other
            continue

        if color == BLACK:
            start = time.perf_counter()
            move = ai.choose_move(board, color, moves)
            elapsed = time.perf_counter() - start
            assert elapsed < 0.3
        else:
            move = rng.choice(moves)

        assert move in moves
        board = apply_move(board, move, color)
        next_color = next_turn_color(board, color)
        if next_color is None:
            break
        color = next_color
    else:
        raise AssertionError("simulated game did not terminate")
