from __future__ import annotations

import math
import time
from dataclasses import dataclass
from functools import lru_cache

BOARD_SIZE = 8
EMPTY = "."
BLACK = "B"
WHITE = "W"
FILES = "abcdefgh"
INF = 1_000_000_000
FULL_BOARD = (1 << 64) - 1

A_FILE = 0x0101010101010101
H_FILE = 0x8080808080808080
NOT_A_FILE = FULL_BOARD ^ A_FILE
NOT_H_FILE = FULL_BOARD ^ H_FILE

EXACT = 0
LOWER_BOUND = 1
UPPER_BOUND = 2

Board = list[list[str]]
BoardTuple = tuple[tuple[str, ...], ...]

POSITION_WEIGHTS = (
    (120, -30, 25, 8, 8, 25, -30, 120),
    (-30, -60, -12, -8, -8, -12, -60, -30),
    (25, -12, 18, 5, 5, 18, -12, 25),
    (8, -8, 5, 2, 2, 5, -8, 8),
    (8, -8, 5, 2, 2, 5, -8, 8),
    (25, -12, 18, 5, 5, 18, -12, 25),
    (-30, -60, -12, -8, -8, -12, -60, -30),
    (120, -30, 25, 8, 8, 25, -30, 120),
)

SQUARE_NAMES = tuple(f"{FILES[col]}{row + 1}" for row in range(BOARD_SIZE) for col in range(BOARD_SIZE))
MOVE_TO_BIT = {name: 1 << index for index, name in enumerate(SQUARE_NAMES)}
BIT_TO_MOVE = {1 << index: name for index, name in enumerate(SQUARE_NAMES)}
SQUARE_WEIGHTS = tuple(POSITION_WEIGHTS[row][col] for row in range(BOARD_SIZE) for col in range(BOARD_SIZE))

CORNER_BITS = MOVE_TO_BIT["a1"] | MOVE_TO_BIT["h1"] | MOVE_TO_BIT["a8"] | MOVE_TO_BIT["h8"]
CORNER_DANGER_BITS = {
    MOVE_TO_BIT["a1"]: (
        (MOVE_TO_BIT["b1"], 45),
        (MOVE_TO_BIT["a2"], 45),
        (MOVE_TO_BIT["b2"], 75),
    ),
    MOVE_TO_BIT["h1"]: (
        (MOVE_TO_BIT["g1"], 45),
        (MOVE_TO_BIT["h2"], 45),
        (MOVE_TO_BIT["g2"], 75),
    ),
    MOVE_TO_BIT["a8"]: (
        (MOVE_TO_BIT["b8"], 45),
        (MOVE_TO_BIT["a7"], 45),
        (MOVE_TO_BIT["b7"], 75),
    ),
    MOVE_TO_BIT["h8"]: (
        (MOVE_TO_BIT["g8"], 45),
        (MOVE_TO_BIT["h7"], 45),
        (MOVE_TO_BIT["g7"], 75),
    ),
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


@dataclass(slots=True)
class TTEntry:
    depth: int
    score: float
    flag: int
    best_move: int


def create_initial_board() -> Board:
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    board[3][3] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    board[4][4] = WHITE
    return board


def opponent(color: str) -> str:
    normalized = _normalize_color(color)
    if normalized == BLACK:
        return WHITE
    return BLACK


def legal_moves(board: Board | BoardTuple, color: str) -> list[str]:
    player, other = _board_to_player_bits(board, color)
    return [_move_name(move_bit) for move_bit in _iter_bits(_legal_bits(player, other))]


def apply_move(board: Board | BoardTuple, move: str, color: str) -> Board:
    normalized = _normalize_color(color)
    black_bits, white_bits = _board_to_color_bits(board)
    player, other = (black_bits, white_bits) if normalized == BLACK else (white_bits, black_bits)
    player, other = _apply_move_bits(player, other, _move_bit(move))
    if normalized == BLACK:
        return _bits_to_board(player, other)
    return _bits_to_board(other, player)


def next_turn_color(board: Board | BoardTuple, current_color: str) -> str | None:
    current = _normalize_color(current_color)
    black_bits, white_bits = _board_to_color_bits(board)
    player, other = (black_bits, white_bits) if current == BLACK else (white_bits, black_bits)

    if _legal_bits(other, player):
        return WHITE if current == BLACK else BLACK
    if _legal_bits(player, other):
        return current
    return None


def score(board: Board | BoardTuple) -> tuple[int, int]:
    black_bits, white_bits = _board_to_color_bits(board)
    return black_bits.bit_count(), white_bits.bit_count()


def _normalize_color(color: str) -> str:
    normalized = color.strip().lower()
    if normalized in {"b", "black"}:
        return BLACK
    if normalized in {"w", "white"}:
        return WHITE
    raise ValueError(f"Unsupported color: {color}")


def _move_bit(move: str) -> int:
    try:
        return MOVE_TO_BIT[move.lower()]
    except KeyError as exc:
        raise ValueError(f"Invalid move format: {move}") from exc


def _move_name(move_bit: int) -> str:
    return BIT_TO_MOVE[move_bit]


def _board_to_color_bits(board: Board | BoardTuple) -> tuple[int, int]:
    black_bits = 0
    white_bits = 0
    for row_index, row in enumerate(board):
        for col_index, cell in enumerate(row):
            bit = 1 << (row_index * BOARD_SIZE + col_index)
            if cell == BLACK:
                black_bits |= bit
            elif cell == WHITE:
                white_bits |= bit
    return black_bits, white_bits


def _board_to_player_bits(board: Board | BoardTuple, color: str) -> tuple[int, int]:
    black_bits, white_bits = _board_to_color_bits(board)
    if _normalize_color(color) == BLACK:
        return black_bits, white_bits
    return white_bits, black_bits


def _bits_to_board(black_bits: int, white_bits: int) -> Board:
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for index in range(64):
        bit = 1 << index
        row = index // BOARD_SIZE
        col = index % BOARD_SIZE
        if black_bits & bit:
            board[row][col] = BLACK
        elif white_bits & bit:
            board[row][col] = WHITE
    return board


def _shift_north(bits: int) -> int:
    return (bits << 8) & FULL_BOARD


def _shift_south(bits: int) -> int:
    return bits >> 8


def _shift_east(bits: int) -> int:
    return ((bits & NOT_H_FILE) << 1) & FULL_BOARD


def _shift_west(bits: int) -> int:
    return (bits & NOT_A_FILE) >> 1


def _shift_north_east(bits: int) -> int:
    return ((bits & NOT_H_FILE) << 9) & FULL_BOARD


def _shift_north_west(bits: int) -> int:
    return ((bits & NOT_A_FILE) << 7) & FULL_BOARD


def _shift_south_east(bits: int) -> int:
    return (bits & NOT_H_FILE) >> 7


def _shift_south_west(bits: int) -> int:
    return (bits & NOT_A_FILE) >> 9


SHIFTS = (
    _shift_north,
    _shift_south,
    _shift_east,
    _shift_west,
    _shift_north_east,
    _shift_north_west,
    _shift_south_east,
    _shift_south_west,
)


def _neighbors(bits: int) -> int:
    adjacent = 0
    for shift in SHIFTS:
        adjacent |= shift(bits)
    return adjacent


@lru_cache(maxsize=500_000)
def _legal_bits(player: int, other: int) -> int:
    empty = ~(player | other) & FULL_BOARD
    moves = 0
    for shift in SHIFTS:
        captured = shift(player) & other
        for _ in range(5):
            captured |= shift(captured) & other
        moves |= shift(captured) & empty
    return moves


@lru_cache(maxsize=500_000)
def _apply_move_bits(player: int, other: int, move_bit: int) -> tuple[int, int]:
    flips = 0
    for shift in SHIFTS:
        captured = 0
        current = shift(move_bit)
        while current & other:
            captured |= current
            current = shift(current)
        if current & player:
            flips |= captured

    if not flips:
        raise ValueError(f"Illegal move {_move_name(move_bit)}")

    player |= move_bit | flips
    other &= ~flips
    return player, other


def _iter_bits(bits: int):
    while bits:
        move = bits & -bits
        yield move
        bits ^= move


def _weighted_sum(bits: int) -> int:
    total = 0
    while bits:
        bit = bits & -bits
        total += SQUARE_WEIGHTS[bit.bit_length() - 1]
        bits ^= bit
    return total


def _ratio(player_value: int, other_value: int) -> float:
    total = player_value + other_value
    if total == 0:
        return 0.0
    return 100.0 * (player_value - other_value) / total


def _corner_danger_score(player: int, other: int) -> int:
    score_value = 0
    occupied = player | other
    for corner, danger_squares in CORNER_DANGER_BITS.items():
        if occupied & corner:
            continue
        for square, penalty in danger_squares:
            if player & square:
                score_value -= penalty
            elif other & square:
                score_value += penalty
    return score_value


def _stable_edge_count(bits: int) -> int:
    total = 0
    corners = (
        (MOVE_TO_BIT["a1"], (1, 8)),
        (MOVE_TO_BIT["h1"], (-1, 8)),
        (MOVE_TO_BIT["a8"], (1, -8)),
        (MOVE_TO_BIT["h8"], (-1, -8)),
    )
    for corner, deltas in corners:
        if not bits & corner:
            continue
        total += 1
        corner_index = corner.bit_length() - 1
        for delta in deltas:
            index = corner_index + delta
            while 0 <= index < 64:
                col = index % BOARD_SIZE
                previous_col = (index - delta) % BOARD_SIZE
                if abs(col - previous_col) > 1:
                    break
                bit = 1 << index
                if not bits & bit:
                    break
                total += 1
                index += delta
    return total


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
        self._tt: dict[tuple[int, int], TTEntry] = {}
        self.last_stats = SearchStats(move="pass", score=0.0, completed_depth=0, nodes=0, elapsed_seconds=0.0)

    def choose_move(self, board: Board, color: str, legal_moves_from_server: list[str]) -> str:
        start = time.perf_counter()
        normalized_color = _normalize_color(color)
        provided_moves = tuple(dict.fromkeys(move.lower() for move in legal_moves_from_server))
        if not provided_moves:
            self.last_stats = SearchStats("pass", 0.0, 0, 0, time.perf_counter() - start)
            return "pass"

        player, other = _board_to_player_bits(board, normalized_color)
        legal = _legal_bits(player, other)
        provided_bits = tuple(_move_bit(move) for move in provided_moves if _move_bit(move) & legal)
        if not provided_bits:
            fallback = provided_moves[0]
            self.last_stats = SearchStats(fallback, 0.0, 0, 0, time.perf_counter() - start)
            return fallback

        best_move = self._best_static_move(player, other, provided_bits)
        best_score = -math.inf
        completed_depth = 0
        self.nodes = 0
        self._tt.clear()
        self.deadline = start + max(0.0, self.move_budget_seconds)

        target_depth = self._target_depth(player, other)
        previous_best = best_move
        for depth in range(1, target_depth + 1):
            if time.perf_counter() >= self.deadline:
                break
            try:
                candidate, score_value = self._root_search(player, other, provided_bits, depth, previous_best)
            except SearchTimeout:
                break
            if candidate:
                best_move = candidate
                previous_best = candidate
                best_score = score_value
                completed_depth = depth

        move_name = _move_name(best_move)
        self.last_stats = SearchStats(
            move=move_name,
            score=best_score if best_score != -math.inf else 0.0,
            completed_depth=completed_depth,
            nodes=self.nodes,
            elapsed_seconds=time.perf_counter() - start,
        )
        return move_name

    def _target_depth(self, player: int, other: int) -> int:
        empty_count = 64 - (player | other).bit_count()
        if empty_count <= self.exact_empty_threshold:
            return min(self.max_depth, empty_count + 2)
        return self.max_depth

    def _root_search(
        self,
        player: int,
        other: int,
        moves: tuple[int, ...],
        depth: int,
        preferred_move: int,
    ) -> tuple[int, float]:
        self._check_time()
        alpha = -math.inf
        beta = math.inf
        best_score = -math.inf
        best_move = preferred_move

        for move in self._ordered_moves(player, other, moves, preferred_move):
            self._check_time()
            next_player, next_other = _apply_move_bits(player, other, move)
            score_value = self._child_score(next_player, next_other, depth - 1, alpha, beta)
            if score_value > best_score:
                best_score = score_value
                best_move = move
            alpha = max(alpha, best_score)
        return best_move, best_score

    def _search(self, player: int, other: int, depth: int, alpha: float, beta: float) -> float:
        self._check_time()
        self.nodes += 1

        moves = _legal_bits(player, other)
        if not moves:
            if not _legal_bits(other, player):
                return self._terminal_score(player, other)
            if depth <= 0:
                return self._evaluate(player, other)
            return -self._search(other, player, depth - 1, -beta, -alpha)

        if depth <= 0:
            return self._evaluate(player, other)

        alpha_original = alpha
        tt_key = (player, other)
        entry = self._tt.get(tt_key)
        preferred_move = 0
        if entry is not None:
            preferred_move = entry.best_move
            if entry.depth >= depth:
                if entry.flag == EXACT:
                    return entry.score
                if entry.flag == LOWER_BOUND:
                    alpha = max(alpha, entry.score)
                elif entry.flag == UPPER_BOUND:
                    beta = min(beta, entry.score)
                if alpha >= beta:
                    return entry.score

        best_score = -math.inf
        best_move = preferred_move
        move_list = tuple(_iter_bits(moves))
        first_move = True

        for move in self._ordered_moves(player, other, move_list, preferred_move):
            next_player, next_other = _apply_move_bits(player, other, move)
            if first_move:
                score_value = self._child_score(next_player, next_other, depth - 1, alpha, beta)
                first_move = False
            else:
                score_value = self._child_score(next_player, next_other, depth - 1, alpha, alpha + 1)
                if alpha < score_value < beta:
                    score_value = self._child_score(next_player, next_other, depth - 1, alpha, beta)

            if score_value > best_score:
                best_score = score_value
                best_move = move
            alpha = max(alpha, score_value)
            if alpha >= beta:
                break

        if best_score <= alpha_original:
            flag = UPPER_BOUND
        elif best_score >= beta:
            flag = LOWER_BOUND
        else:
            flag = EXACT
        self._tt[tt_key] = TTEntry(depth=depth, score=best_score, flag=flag, best_move=best_move)
        return best_score

    def _child_score(self, player: int, other: int, depth: int, alpha: float, beta: float) -> float:
        if _legal_bits(other, player):
            return -self._search(other, player, depth, -beta, -alpha)
        if _legal_bits(player, other):
            return self._search(player, other, depth, alpha, beta)
        return self._terminal_score(player, other)

    def _best_static_move(self, player: int, other: int, moves: tuple[int, ...]) -> int:
        return max(moves, key=lambda move: self._move_order_score(player, other, move))

    def _ordered_moves(self, player: int, other: int, moves: tuple[int, ...], preferred_move: int = 0) -> list[int]:
        ordered = sorted(moves, key=lambda move: self._move_order_score(player, other, move), reverse=True)
        if preferred_move in ordered:
            ordered.remove(preferred_move)
            ordered.insert(0, preferred_move)
        return ordered

    def _move_order_score(self, player: int, other: int, move: int) -> float:
        index = move.bit_length() - 1
        score_value = float(SQUARE_WEIGHTS[index])
        if move & CORNER_BITS:
            score_value += 100_000

        next_player, next_other = _apply_move_bits(player, other, move)
        opponent_moves = _legal_bits(next_other, next_player)
        own_moves = _legal_bits(next_player, next_other)
        score_value += (move & CORNER_BITS).bit_count() * 60_000
        score_value -= (opponent_moves & CORNER_BITS).bit_count() * 80_000
        score_value += (own_moves & CORNER_BITS).bit_count() * 20_000
        score_value -= self._danger_after_move(player, other, move) * 900
        score_value -= opponent_moves.bit_count() * 35
        score_value += own_moves.bit_count() * 12
        score_value += (next_player.bit_count() - player.bit_count()) * 2
        if not opponent_moves and own_moves:
            score_value += 2_000
        return score_value

    def _danger_after_move(self, player: int, other: int, move: int) -> int:
        occupied = player | other
        danger = 0
        for corner, danger_squares in CORNER_DANGER_BITS.items():
            if occupied & corner:
                continue
            for square, penalty in danger_squares:
                if move & square:
                    danger += penalty
        return danger

    def _evaluate(self, player: int, other: int) -> float:
        occupied = player | other
        empty = (~occupied) & FULL_BOARD
        empty_count = empty.bit_count()

        player_moves = _legal_bits(player, other)
        other_moves = _legal_bits(other, player)
        if not player_moves and not other_moves:
            return self._terminal_score(player, other)

        if empty_count > 44:
            disc_weight = 1
            mobility_weight = 95
            potential_weight = 40
            frontier_weight = 35
            positional_weight = 4
            corner_weight = 1_600
            stable_weight = 150
        elif empty_count > 16:
            disc_weight = 6
            mobility_weight = 80
            potential_weight = 30
            frontier_weight = 25
            positional_weight = 3
            corner_weight = 1_800
            stable_weight = 190
        else:
            disc_weight = 90
            mobility_weight = 35
            potential_weight = 10
            frontier_weight = 8
            positional_weight = 1
            corner_weight = 2_200
            stable_weight = 260

        player_count = player.bit_count()
        other_count = other.bit_count()
        player_frontier = (player & _neighbors(empty)).bit_count()
        other_frontier = (other & _neighbors(empty)).bit_count()
        player_potential = (empty & _neighbors(other)).bit_count()
        other_potential = (empty & _neighbors(player)).bit_count()
        player_stable = _stable_edge_count(player)
        other_stable = _stable_edge_count(other)
        positional = _weighted_sum(player) - _weighted_sum(other)

        return (
            disc_weight * _ratio(player_count, other_count)
            + mobility_weight * _ratio(player_moves.bit_count(), other_moves.bit_count())
            + potential_weight * _ratio(player_potential, other_potential)
            - frontier_weight * _ratio(player_frontier, other_frontier)
            + positional_weight * positional
            + corner_weight * ((player & CORNER_BITS).bit_count() - (other & CORNER_BITS).bit_count())
            + 1_100 * ((player_moves & CORNER_BITS).bit_count() - (other_moves & CORNER_BITS).bit_count())
            + stable_weight * (player_stable - other_stable)
            + _corner_danger_score(player, other)
        )

    def _terminal_score(self, player: int, other: int) -> float:
        diff = player.bit_count() - other.bit_count()
        if diff > 0:
            return INF + diff
        if diff < 0:
            return -INF + diff
        return 0.0

    def _check_time(self) -> None:
        if time.perf_counter() >= self.deadline:
            raise SearchTimeout
