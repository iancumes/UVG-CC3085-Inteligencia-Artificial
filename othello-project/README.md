# Othello Tournament MVP

Small FastAPI-based Othello/Reversi tournament server with SQLite persistence, WebSocket bot play, Swiss-style pairings, and a reusable Python bot client.

## Features

- Server-authoritative Othello rules engine for 8x8 play
- Player registration with unique client tokens
- WebSocket bot connectivity with reconnect support
- 3-second move deadlines by default, configurable with `MOVE_TIMEOUT_SECONDS`
- Swiss-style round pairing with repeat-avoidance when possible
- SQLite persistence for players, tournaments, rounds, games, standings, and move logs
- pytest coverage for rules, pairing, illegal move loss, and timeout loss
- Docker and docker-compose support

## Project Layout

```text
server/
  main.py
  game_rules.py
  tournament.py
  pairing.py
  models.py
  db.py
  schemas.py
client/
  bot_client.py
  sample_bot.py
tests/
  test_game_rules.py
  test_game_flow.py
  test_pairing.py
Dockerfile
docker-compose.yml
README.md
```

## Setup

### Local

```bash
cd othello-project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Docker

```bash
cd othello-project
docker compose up --build
```

## Run The Server

```bash
cd othello-project
export MOVE_TIMEOUT_SECONDS=3
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123
uvicorn server.main:app --reload
```

The server creates SQLite data in `./othello.db` by default. Override with `DATABASE_URL`.

Default admin credentials are:

```text
username: admin
password: admin123
```

Override them with `ADMIN_USERNAME` and `ADMIN_PASSWORD`.

## Register Players

Players are enrolled per tournament, not globally.

First create a tournament and open registration from the admin API, then enroll bots into that specific tournament:

```bash
curl -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Use the returned token to create a tournament and open registration:

```bash
curl -X POST http://localhost:8000/admin/tournaments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name":"Campus Cup","total_rounds":3}'

curl -X POST http://localhost:8000/admin/tournaments/1/start-registration \
  -H "Authorization: Bearer <token>"
```

Then a bot enrollment looks like:

```bash
curl -X POST http://localhost:8000/players \
  -H "Content-Type: application/json" \
  -d '{"tournament_id":1,"name":"bot-a"}'
```

Example response:

```json
{
  "tournament_id": 1,
  "player_id": 1,
  "name": "bot-a",
  "client_token": "generated-by-server"
}
```

Usernames must be unique within a tournament. If the username is already taken in that tournament, enrollment is rejected.

## Run A Sample Bot

Create a tournament, open registration, then run one process per bot:

```bash
python -m client.sample_bot --server-url http://localhost:8000 --tournament-id 1 --username bot-a
python -m client.sample_bot --server-url http://localhost:8000 --tournament-id 1 --username bot-b
```

Each bot will:

1. Enroll itself in that specific tournament using its username.
2. Receive a server-generated player ID and token.
3. Connect to the WebSocket automatically.

If the username is already taken in that tournament, the bot exits with an enrollment error.

## Tournament Flow

1. Create a tournament with `POST /admin/tournaments`.
2. Open tournament registration with `POST /admin/tournaments/{id}/start-registration`.
3. Start bot clients with `--tournament-id` and `--username` so they enroll into that tournament.
4. Close registration with `POST /admin/tournaments/{id}/close-registration`.
5. Start the tournament with `POST /admin/tournaments/{id}/start`.
6. Start rounds with `POST /admin/rounds/{roundId}/start`.
7. Inspect standings at `GET /standings?tournament_id={id}` or `GET /admin/standings`.
8. Inspect any game log at `GET /games/{game_id}`.

If the player count is odd, the lowest-ranked eligible player receives a 1-point bye.

## HTTP And WebSocket API

### `POST /players`

Request:

```json
{
  "tournament_id": 1,
  "name": "bot-a"
}
```

Response includes a generated `client_token` and `player_id`.

### `GET /standings`

Returns standings for the active/latest tournament, or for a specific tournament with `?tournament_id=...`.

### `GET /games/{game_id}`

Returns the persisted game state plus every stored move and board snapshot.

### Admin API

Admin authentication:

```http
POST /admin/login
```

Request:

```json
{
  "username": "admin",
  "password": "admin123"
}
```

Admin endpoints require:

```http
Authorization: Bearer <token>
```

Available admin endpoints:

- `GET /admin/tournaments`
- `POST /admin/tournaments`
- `GET /admin/tournaments/{id}`
- `POST /admin/tournaments/{id}/start-registration`
- `POST /admin/tournaments/{id}/close-registration`
- `POST /admin/tournaments/{id}/start`
- `POST /admin/rounds/{roundId}/start`
- `GET /admin/rounds/{roundId}`
- `GET /admin/games/{gameId}`
- `POST /admin/games/{gameId}/force-end`
- `POST /admin/players/{playerId}/forfeit`
- `GET /admin/players`
- `GET /admin/standings`
- `GET /admin/live-games`

Admin WebSocket:

- `WS /admin/ws?token=<token>`

The admin WebSocket emits:

- `tournament_update`
- `player_connected`
- `player_disconnected`
- `round_started`
- `game_started`
- `game_update`
- `game_over`
- `move_recorded`
- `illegal_move`
- `timeout`
- `forfeit`

### `WS /ws/{player_id}?token=...`

Bots connect here and exchange JSON messages.

Server to client:

```json
{
  "type": "your_turn",
  "game_id": "uuid",
  "color": "black",
  "board": [[".", ".", ".", ".", ".", ".", ".", "."], ["...", "..."]],
  "legal_moves": ["d3", "c4", "f5", "e6"],
  "deadline_ms": 3000
}
```

```json
{
  "type": "game_update",
  "game_id": "uuid",
  "board": [[".", ".", ".", ".", ".", ".", ".", "."], ["...", "..."]],
  "next_player": "white",
  "last_move": "d3"
}
```

```json
{
  "type": "game_over",
  "game_id": "uuid",
  "black_score": 34,
  "white_score": 30,
  "result": "black_win"
}
```

Client to server:

```json
{
  "type": "move",
  "game_id": "uuid",
  "move": "d3"
}
```

## Rules And Enforcement

- The server is the only authority on board state.
- Illegal moves immediately forfeit the game.
- Missing the move deadline immediately forfeits the game.
- Disconnecting during a turn is treated like silence; reconnecting is allowed, but the original deadline still applies.
- If a player has no legal move, the server automatically records a pass and continues.

## Tests

```bash
cd othello-project
pytest
```

## Known MVP Limitations

- Only one active tournament is supported at a time.
- Pairing is greedy Swiss, not a full constraint solver.
- There is no authentication layer beyond player token matching.
- Tournament rounds are started manually through admin endpoints.
- Reconnected players receive live turn prompts, but there is no separate full-state resync endpoint outside the normal game messages.
