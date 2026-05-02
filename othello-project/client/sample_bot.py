from __future__ import annotations

import asyncio
import logging
import time 

from client.bot_client import BotClient, build_arg_parser


def choose_move(board: list[list[str]], color: str, legal_moves: list[str]) -> str:
    if not legal_moves:
        return "pass"
    time.sleep(2)
    return legal_moves[0]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_arg_parser().parse_args()
    client = BotClient(
        server_url=args.server_url,
        tournament_id=args.tournament_id,
        username=args.username,
        choose_move=choose_move,
    )
    asyncio.run(client.run_forever())


if __name__ == "__main__":
    main()
