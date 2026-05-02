# Client

This directory contains the reusable Python bot client and the sample bot.

## Files

- `bot_client.py`: transport layer that enrolls a bot, opens the WebSocket, receives turn messages, and sends moves
- `sample_bot.py`: example bot implementation with a very simple move selector

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
python -m client.sample_bot --server-url http://localhost:8000 --tournament-id 1 --username bot-a
```

You can run multiple bots in separate terminals by changing `--username`.

## How the client works

1. `BotClient._enroll()` sends `POST /players` with `tournament_id` and `username`.
2. The server returns `player_id` and `client_token`.
3. `BotClient.run_forever()` connects to `WS /ws/{player_id}?token=...`.
4. When the server sends a `your_turn` message, `BotClient._choose_move()` calls your `choose_move` function.
5. The chosen move is sent back as `{ "type": "move", "game_id": ..., "move": ... }`.

## Where to change the sample bot to make smarter decisions

The main place to change is `sample_bot.py`.

Right now the sample implementation:

- waits 2 seconds
- returns `legal_moves[0]`

That means it always plays the first legal move, which is intentionally weak.

## Recommended upgrade path for smarter play

### Start with `choose_move`

Replace the current strategy with logic that scores each legal move and returns the best one.

Useful ideas:

- prefer corners: `a1`, `a8`, `h1`, `h8`
- avoid squares next to empty corners early in the game
- prefer moves that leave the opponent fewer legal replies
- prefer moves that increase your stable discs late in the game
- use a shallow minimax search with alpha-beta pruning if you want a stronger bot

## What code changes first

The first function to rewrite is:

```python
def choose_move(board: list[list[str]], color: str, legal_moves: list[str]) -> str:
```

That function is the strategy hook used by `BotClient`.

## If you want a much stronger bot

You will probably add:

- helper functions in `sample_bot.py` for board evaluation
- a move simulator that applies candidate moves
- opponent modeling to estimate the next reply

If you do that, the reusable connection code in `bot_client.py` usually does not need to change.

## What usually does not need to change

- enrollment logic in `BotClient._enroll()`
- reconnect logic in `BotClient.run_forever()`
- WebSocket message handling in `BotClient._run_connection()`

Those are transport concerns. The intelligence belongs in `choose_move`.
