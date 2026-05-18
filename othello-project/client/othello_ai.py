from __future__ import annotations

import math
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

BOARD_SIZE = 8
EMPTY = "."
BLACK = "B"
WHITE = "W"
FILES = "abcdefgh"
INF = 1_000_000_000

Board = list[list[str]]
BoardTuple = tuple[tuple[str, ...], ...]

DIRECTIONS = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

POSITION_WEIGHTS = (
    (120, -20, 20, 5, 5, 20, -20, 120),
    (-20, -40, -5, -5, -5, -5, -40, -20),
    (20, -5, 15, 3, 3, 15, -5, 20),
    (5, -5, 3, 3, 3, 3, -5, 5),
    (5, -5, 3, 3, 3, 3, -5, 5),
    (20, -5, 15, 3, 3, 15, -5, 20),
    (-20, -40, -5, -5, -5, -5, -40, -20),
    (120, -20, 20, 5, 5, 20, -20, 120),
)

CORNERS = ((0, 0), (0, 7), (7, 0), (7, 7))
CORNER_MOVES = frozenset(("a1", "h1", "a8", "h8"))
CORNER_DANGER = {
    (0, 0): (((0, 1), 35), ((1, 0), 35), ((1, 1), 55)),
    (0, 7): (((0, 6), 35), ((1, 7), 35), ((1, 6), 55)),
    (7, 0): (((7, 1), 35), ((6, 0), 35), ((6, 1), 55)),
    (7, 7): (((7, 6), 35), ((6, 7), 35), ((6, 6), 55)),
}


class SearchTimeout(Exception):
    pass


@dataclass(slots=True)
class SearchStats:
    move: str
    score: float
    completed_depth: int
    nodes: int
    elapsed_seconds: float


def create_initial_board() -> Board:
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    board[3][3] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    board[4][4] = WHITE
    return board


def opponent(color: str) -> str:
    if color == BLACK:
        return WHITE
    if color == WHITE:
        return BLACK
    raise ValueError(f"Unsupported color: {color}")


def legal_moves(board: Board | BoardTuple, color: str) -> list[str]:
    return list(_legal_moves_tuple(_to_tuple(board), color))


def apply_move(board: Board | BoardTuple, move: str, color: str) -> Board:
    return _to_list(_apply_move_tuple(_to_tuple(board), move.lower(), color))


def next_turn_color(board: Board | BoardTuple, current_color: str) -> str | None:
    return _next_turn_color(_to_tuple(board), current_color)


def score(board: Board | BoardTuple) -> tuple[int, int]:
    board_tuple = _to_tuple(board)
    black_score = sum(cell == BLACK for row in board_tuple for cell in row)
    white_score = sum(cell == WHITE for row in board_tuple for cell in row)
    return black_score, white_score


def _to_tuple(board: Board | BoardTuple) -> BoardTuple:
    return tuple(tuple(row) for row in board)


def _to_list(board: BoardTuple) -> Board:
    return [list(row) for row in board]


def _inside(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def _position_to_move(row: int, col: int) -> str:
    return f"{FILES[col]}{row + 1}"


def _move_to_position(move: str) -> tuple[int, int]:
    if len(move) != 2:
        raise ValueError(f"Invalid move format: {move}")
    file_char = move[0].lower()
    rank_char = move[1]
    if file_char not in FILES or rank_char not in "12345678":
        raise ValueError(f"Invalid move format: {move}")
    return int(rank_char) - 1, FILES.index(file_char)


def _captures_in_direction(
    board: BoardTuple,
    row: int,
    col: int,
    color: str,
    dr: int,
    dc: int,
) -> tuple[tuple[int, int], ...]:
    captured: list[tuple[int, int]] = []
    current_row = row + dr
    current_col = col + dc
    other = opponent(color)

    while _inside(current_row, current_col) and board[current_row][current_col] == other:
        captured.append((current_row, current_col))
        current_row += dr
        current_col += dc

    if not captured:
        return ()
    if not _inside(current_row, current_col):
        return ()
    if board[current_row][current_col] != color:
        return ()
    return tuple(captured)


@lru_cache(maxsize=250_000)
def _captured_discs_tuple(board: BoardTuple, move: str, color: str) -> tuple[tuple[int, int], ...]:
    row, col = _move_to_position(move)
    if board[row][col] != EMPTY:
        return ()

    captured: list[tuple[int, int]] = []
    for dr, dc in DIRECTIONS:
        captured.extend(_captures_in_direction(board, row, col, color, dr, dc))
    return tuple(captured)


@lru_cache(maxsize=250_000)
def _legal_moves_tuple(board: BoardTuple, color: str) -> tuple[str, ...]:
    moves: list[str] = []
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != EMPTY:
                continue
            move = _position_to_move(row, col)
            if _captured_discs_tuple(board, move, color):
                moves.append(move)
    return tuple(moves)


@lru_cache(maxsize=250_000)
def _apply_move_tuple(board: BoardTuple, move: str, color: str) -> BoardTuple:
    flips = _captured_discs_tuple(board, move, color)
    if not flips:
        raise ValueError(f"Illegal move {move} for color {color}")

    updated = [list(row) for row in board]
    row, col = _move_to_position(move)
    updated[row][col] = color
    for flip_row, flip_col in flips:
        updated[flip_row][flip_col] = color
    return tuple(tuple(row) for row in updated)


def _next_turn_color(board: BoardTuple, current_color: str) -> str | None:
    other = opponent(current_color)
    if _legal_moves_tuple(board, other):
        return other
    if _legal_moves_tuple(board, current_color):
        return current_color
    return None


def _empty_count(board: BoardTuple) -> int:
    return sum(cell == EMPTY for row in board for cell in row)


def _disc_count(board: BoardTuple, color: str) -> int:
    return sum(cell == color for row in board for cell in row)


def _ratio(own_value: int, opponent_value: int) -> float:
    total = own_value + opponent_value
    if total == 0:
        return 0.0
    return 100.0 * (own_value - opponent_value) / total


def _is_corner(row: int, col: int) -> bool:
    return (row, col) in CORNERS


def _corner_move_count(moves: tuple[str, ...]) -> int:
    return sum(move in CORNER_MOVES for move in moves)


def _corner_danger_penalty(board: BoardTuple, move: str) -> int:
    row, col = _move_to_position(move)
    penalty = 0
    for corner, danger_squares in CORNER_DANGER.items():
        if board[corner[0]][corner[1]] != EMPTY:
            continue
        for square, square_penalty in danger_squares:
            if (row, col) == square:
                penalty += square_penalty
    return penalty


def _frontier_count(board: BoardTuple, color: str) -> int:
    total = 0
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != color:
                continue
            if any(
                _inside(row + dr, col + dc) and board[row + dr][col + dc] == EMPTY
                for dr, dc in DIRECTIONS
            ):
                total += 1
    return total


def _stable_edge_count(board: BoardTuple, color: str) -> int:
    stable: set[tuple[int, int]] = set()
    scans = {
        (0, 0): ((0, 1), (1, 0)),
        (0, 7): ((0, -1), (1, 0)),
        (7, 0): ((0, 1), (-1, 0)),
        (7, 7): ((0, -1), (-1, 0)),
    }

    for corner, directions in scans.items():
        if board[corner[0]][corner[1]] != color:
            continue
        stable.add(corner)
        for dr, dc in directions:
            row = corner[0] + dr
            col = corner[1] + dc
            while _inside(row, col) and board[row][col] == color:
                stable.add((row, col))
                row += dr
                col += dc
    return len(stable)


class OthelloAI:
    def __init__(
        self,
        move_budget_seconds: float = 2.75,
        max_depth: int = 64,
        exact_empty_threshold: int = 14,
    ) -> None:
        self.move_budget_seconds = move_budget_seconds
        self.max_depth = max_depth
        self.exact_empty_threshold = exact_empty_threshold
        self.deadline = 0.0
        self.nodes = 0
        self._transposition: dict[tuple[BoardTuple, str, int], tuple[float, str | None]] = {}
        self._move_hints: dict[tuple[BoardTuple, str], str] = {}
        self.last_stats = SearchStats(move="pass", score=0.0, completed_depth=0, nodes=0, elapsed_seconds=0.0)

    def choose_move(self, board: Board, color: str, legal_moves_from_server: list[str]) -> str:
        start = time.perf_counter()
        provided_moves = tuple(dict.fromkeys(move.lower() for move in legal_moves_from_server))
        if not provided_moves:
            self.last_stats = SearchStats(
                move="pass",
                score=0.0,
                completed_depth=0,
                nodes=0,
                elapsed_seconds=time.perf_counter() - start,
            )
            return "pass"

        board_tuple = _to_tuple(board)
        fallback = self._best_static_move(board_tuple, color, provided_moves) or provided_moves[0]
        best_move = fallback
        best_score = -math.inf
        completed_depth = 0
        self.nodes = 0
        self._transposition.clear()
        self._move_hints.clear()
        self.deadline = start + max(0.0, self.move_budget_seconds)

        target_depth = self._target_depth(board_tuple)
        root_hint: str | None = None
        for depth in range(1, target_depth + 1):
            if time.perf_counter() >= self.deadline:
                break
            try:
                move, score_value = self._search_root(board_tuple, color, provided_moves, depth, root_hint)
            except SearchTimeout:
                break

            if move in provided_moves:
                best_move = move
                root_hint = move
                best_score = score_value
                completed_depth = depth

        if best_move not in provided_moves:
            best_move = fallback

        self.last_stats = SearchStats(
            move=best_move,
            score=best_score if best_score != -math.inf else 0.0,
            completed_depth=completed_depth,
            nodes=self.nodes,
            elapsed_seconds=time.perf_counter() - start,
        )
        return best_move

    def _target_depth(self, board: BoardTuple) -> int:
        empty_squares = _empty_count(board)
        if empty_squares <= self.exact_empty_threshold:
            return min(self.max_depth, empty_squares + 2)
        return self.max_depth

    def _search_root(
        self,
        board: BoardTuple,
        color: str,
        provided_moves: Iterable[str],
        depth: int,
        root_hint: str | None,
    ) -> tuple[str, float]:
        self._check_time()
        ordered_moves = self._ordered_moves(board, color, tuple(provided_moves), preferred_move=root_hint)
        alpha = -math.inf
        beta = math.inf
        best_move = ordered_moves[0]
        best_score = -math.inf

        for move in ordered_moves:
            self._check_time()
            try:
                child = _apply_move_tuple(board, move, color)
            except ValueError:
                continue

            next_color = _next_turn_color(child, color)
            if next_color is None:
                score_value = self._terminal_score(child, color)
            elif next_color == color:
                score_value = self._negamax(child, color, depth - 1, alpha, beta)
            else:
                score_value = -self._negamax(child, next_color, depth - 1, -beta, -alpha)

            if score_value > best_score:
                best_score = score_value
                best_move = move
            alpha = max(alpha, best_score)

        return best_move, best_score

    def _negamax(self, board: BoardTuple, color: str, depth: int, alpha: float, beta: float) -> float:
        self._check_time()
        self.nodes += 1

        moves = _legal_moves_tuple(board, color)
        other = opponent(color)
        if not moves:
            if not _legal_moves_tuple(board, other):
                return self._terminal_score(board, color)
            if depth <= 0:
                return self._evaluate(board, color)
            return -self._negamax(board, other, depth - 1, -beta, -alpha)

        if depth <= 0:
            return self._evaluate(board, color)

        cache_key = (board, color, depth)
        cached = self._transposition.get(cache_key)
        if cached is not None:
            return cached[0]

        best_score = -math.inf
        best_move: str | None = None
        completed_without_cutoff = True
        preferred_move = self._move_hints.get((board, color))
        for move in self._ordered_moves(board, color, moves, preferred_move=preferred_move):
            child = _apply_move_tuple(board, move, color)
            next_color = _next_turn_color(child, color)
            if next_color is None:
                score_value = self._terminal_score(child, color)
            elif next_color == color:
                score_value = self._negamax(child, color, depth - 1, alpha, beta)
            else:
                score_value = -self._negamax(child, next_color, depth - 1, -beta, -alpha)

            if score_value > best_score:
                best_score = score_value
                best_move = move
                self._move_hints[(board, color)] = move
            alpha = max(alpha, score_value)
            if alpha >= beta:
                completed_without_cutoff = False
                break

        if completed_without_cutoff:
            self._transposition[cache_key] = (best_score, best_move)
        return best_score

    def _best_static_move(self, board: BoardTuple, color: str, moves: tuple[str, ...]) -> str | None:
        if not moves:
            return None
        return self._ordered_moves(board, color, moves)[0]

    def _ordered_moves(
        self,
        board: BoardTuple,
        color: str,
        moves: tuple[str, ...],
        preferred_move: str | None = None,
    ) -> list[str]:
        ordered = sorted(moves, key=lambda move: self._move_order_score(board, color, move), reverse=True)
        if preferred_move in ordered:
            ordered.remove(preferred_move)
            ordered.insert(0, preferred_move)
        return ordered

    def _move_order_score(self, board: BoardTuple, color: str, move: str) -> float:
        row, col = _move_to_position(move)
        score_value = float(POSITION_WEIGHTS[row][col])
        if _is_corner(row, col):
            score_value += 10_000

        score_value -= 250 * _corner_danger_penalty(board, move)

        try:
            child = _apply_move_tuple(board, move, color)
        except ValueError:
            return -math.inf

        flips = len(_captured_discs_tuple(board, move, color))
        opponent_moves = _legal_moves_tuple(child, opponent(color))
        own_moves_after = _legal_moves_tuple(child, color)
        score_value += flips * 4
        score_value -= len(opponent_moves) * 25
        score_value += len(own_moves_after) * 8
        score_value -= 5_000 * _corner_move_count(opponent_moves)
        score_value += 2_500 * _corner_move_count(own_moves_after)
        if _next_turn_color(child, color) == color:
            score_value += 350
        return score_value

    def _evaluate(self, board: BoardTuple, color: str) -> float:
        other = opponent(color)
        empty_squares = _empty_count(board)
        own_discs = _disc_count(board, color)
        opponent_discs = _disc_count(board, other)

        if not _legal_moves_tuple(board, color) and not _legal_moves_tuple(board, other):
            return self._terminal_score(board, color)

        if empty_squares > 44:
            disc_weight = 2
            mobility_weight = 85
            frontier_weight = 35
            position_weight = 4
            corner_weight = 1_250
            stable_weight = 120
        elif empty_squares > 16:
            disc_weight = 8
            mobility_weight = 70
            frontier_weight = 25
            position_weight = 3
            corner_weight = 1_300
            stable_weight = 150
        else:
            disc_weight = 70
            mobility_weight = 25
            frontier_weight = 8
            position_weight = 1
            corner_weight = 1_500
            stable_weight = 220

        positional = 0
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if board[row][col] == color:
                    positional += POSITION_WEIGHTS[row][col]
                elif board[row][col] == other:
                    positional -= POSITION_WEIGHTS[row][col]

        own_corners = sum(board[row][col] == color for row, col in CORNERS)
        opponent_corners = sum(board[row][col] == other for row, col in CORNERS)
        own_mobility = len(_legal_moves_tuple(board, color))
        opponent_mobility = len(_legal_moves_tuple(board, other))
        own_corner_moves = _corner_move_count(_legal_moves_tuple(board, color))
        opponent_corner_moves = _corner_move_count(_legal_moves_tuple(board, other))
        own_frontier = _frontier_count(board, color)
        opponent_frontier = _frontier_count(board, other)
        own_stable = _stable_edge_count(board, color)
        opponent_stable = _stable_edge_count(board, other)

        danger_score = self._corner_danger_score(board, color)

        return (
            disc_weight * _ratio(own_discs, opponent_discs)
            + mobility_weight * _ratio(own_mobility, opponent_mobility)
            - frontier_weight * _ratio(own_frontier, opponent_frontier)
            + position_weight * positional
            + corner_weight * (own_corners - opponent_corners)
            + 900 * (own_corner_moves - opponent_corner_moves)
            + stable_weight * (own_stable - opponent_stable)
            + danger_score
        )

    def _corner_danger_score(self, board: BoardTuple, color: str) -> int:
        other = opponent(color)
        score_value = 0
        for corner, danger_squares in CORNER_DANGER.items():
            if board[corner[0]][corner[1]] != EMPTY:
                continue
            for (row, col), penalty in danger_squares:
                if board[row][col] == color:
                    score_value -= penalty
                elif board[row][col] == other:
                    score_value += penalty
        return score_value

    def _terminal_score(self, board: BoardTuple, color: str) -> float:
        own_discs = _disc_count(board, color)
        opponent_discs = _disc_count(board, opponent(color))
        diff = own_discs - opponent_discs
        if diff > 0:
            return INF + diff
        if diff < 0:
            return -INF + diff
        return 0.0

    def _check_time(self) -> None:
        if time.perf_counter() >= self.deadline:
            raise SearchTimeout
