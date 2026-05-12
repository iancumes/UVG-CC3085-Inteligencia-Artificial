# Client

This directory contains the reusable Python bot client and the sample bot.

## Files

- `bot_client.py`: transport layer that enrolls a bot, opens the WebSocket, receives turn messages, and sends moves
- `sample_bot.py`: example bot implementation with a very simple move selector
- `competitive_bot.py`: tournament bot entrypoint that uses the stronger Othello AI
- `othello_ai.py`: minimax/negamax, alpha-beta pruning, iterative deepening, and heuristics

## Dependencies

- Python 3.11+
- Standard library modules such as `asyncio`, `argparse`, `urllib`, and `json`
- `websockets`

Install from the project root:

```bash
cd othello-project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## How to run the sample bot

The backend must already be running and the tournament must already exist with registration open.

```bash
cd othello-project
python -m client.sample_bot --server-url http://localhost:8000 --tournament-name "Spring Open" --username bot-a
```

You can run multiple bots in separate terminals by changing `--username`.

## How to run the competitive bot

Use the same command shape as the sample bot, replacing the module name:

```bash
cd othello-project
python -m client.competitive_bot --server-url http://localhost:8000 --tournament-name "Spring Open" --username bot-a
```

For the remote test server shared in class:

```bash
python -m client.competitive_bot --server-url https://d9df-190-14-11-2.ngrok-free.app --tournament-name test_mayo11 --username your-username
```

More details are documented in `../docs/othello_bot.md`.

## How the client works

1. `BotClient._enroll()` sends `POST /players` with `tournament_name` and `username`.
2. The server returns `player_id` and `client_token`.
3. `BotClient.run_forever()` connects to `WS /ws/{player_id}?token=...`.
4. When the server sends a `your_turn` message, `BotClient._choose_move()` calls your `choose_move` function.
5. The chosen move is sent back as `{ "type": "move", "game_id": ..., "move": ... }`.

## Where to change the sample bot to make smarter decisions

The main place to change is `sample_bot.py`.

Right now the sample implementation:

- waits 2 seconds
- returns a random move from `legal_moves`

That means it plays a random legal move, which is still intentionally weak but a little less predictable.
