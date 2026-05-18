from __future__ import annotations

import asyncio
import logging

from client.bot_client import BotClient, build_arg_parser
from client.othello_ai import OthelloAI

logger = logging.getLogger(__name__)


def main() -> None:
    parser = build_arg_parser()
    parser.description = "Competitive Othello bot for CC3085"
    parser.add_argument("--move-budget-seconds", type=float, default=2.75)
    parser.add_argument("--max-depth", type=int, default=64)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    ai = OthelloAI(move_budget_seconds=args.move_budget_seconds, max_depth=args.max_depth)

    def choose_move(board: list[list[str]], color: str, legal_moves: list[str]) -> str:
        move = ai.choose_move(board, color, legal_moves)
        logger.info(
            "Selected move=%s color=%s depth=%s nodes=%s elapsed=%.4fs score=%.2f",
            move,
            color,
            ai.last_stats.completed_depth,
            ai.last_stats.nodes,
            ai.last_stats.elapsed_seconds,
            ai.last_stats.score,
        )
        return move

    client = BotClient(
        server_url=args.server_url,
        tournament_name=args.tournament_name,
        username=args.username,
        choose_move=choose_move,
    )
    asyncio.run(client.run_forever())


if __name__ == "__main__":
    main()
