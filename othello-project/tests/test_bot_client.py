from __future__ import annotations

import asyncio

from client.bot_client import BotClient
from client.othello_ai import BLACK, create_initial_board, legal_moves


def test_bot_client_passes_deadline_to_four_argument_bot() -> None:
    captured: dict[str, int] = {}
    board = create_initial_board()
    moves = legal_moves(board, BLACK)

    def choose_move(_board: list[list[str]], _color: str, _legal_moves: list[str], deadline_ms: int) -> str:
        captured["deadline_ms"] = deadline_ms
        return _legal_moves[0]

    client = BotClient(
        server_url="http://localhost:8000",
        tournament_name="Test",
        username="bot",
        choose_move=choose_move,
    )

    move = asyncio.run(client._choose_move(board, "black", moves, 1234))

    assert move == moves[0]
    assert captured["deadline_ms"] == 1234


def test_bot_client_keeps_three_argument_bot_compatibility() -> None:
    board = create_initial_board()
    moves = legal_moves(board, BLACK)

    def choose_move(_board: list[list[str]], _color: str, _legal_moves: list[str]) -> str:
        return _legal_moves[-1]

    client = BotClient(
        server_url="http://localhost:8000",
        tournament_name="Test",
        username="bot",
        choose_move=choose_move,
    )

    assert asyncio.run(client._choose_move(board, "black", moves, 1234)) == moves[-1]
