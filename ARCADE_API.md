# RetroChain API Reference

Authoritative reference for interacting with a RetroChain node over REST and gRPC. Everything below reflects the actual protobuf definitions in `proto/retrochain/arcade/v1/*.proto` and the custom routes wired in `app/api_routes.go`.

---

## Endpoints and tools

| Service | Default | Notes |
|---|---|---|
| REST (gRPC-Gateway) | `http://localhost:1317` | Exposes all gRPC queries plus the custom compatibility routes listed below. |
| gRPC | `localhost:9090` | Use `grpcurl -plaintext` locally. |
| gRPC-Web | `http://localhost:9091` | For browser/SDK clients. |
| Tendermint RPC | `http://localhost:26657` | WebSocket at `/websocket`. |
| Swagger | `docs/api/index.html` | Bundled OpenAPI for the node; arcade-specific swagger lives under `proto/retrochain/arcade/v1/*swagger.json`. |
| TypeScript client | `ts-client` | Generated from the protobufs. |

All transactions must be signed (e.g. `retrochaind tx ...` or by POSTing a signed `cosmos.tx.v1beta1.TxRaw` to `/cosmos/tx/v1beta1/txs`). Queries require no auth.

---

## Arcade query API (REST + gRPC)

Each REST path below is also served under the shorter `/arcade/v1/...` prefix. The matching gRPC service is `retrochain.arcade.v1.Query` on port `9090`.

| Purpose | REST path | gRPC method | Key parameters |
|---|---|---|---|
| Module params | `GET /retrochain/arcade/v1/params` | `Query/Params` | - |
| List games | `GET /retrochain/arcade/v1/games` | `Query/ListGames` | `pagination`, `genre`, `active_only` |
| Game by id | `GET /retrochain/arcade/v1/games/{game_id}` | `Query/GetGame` | `game_id` |
| Session by id | `GET /retrochain/arcade/v1/sessions/{session_id}` | `Query/GetSession` | `session_id` |
| Player sessions | `GET /retrochain/arcade/v1/sessions/player/{player}` | `Query/ListPlayerSessions` | `player`, `pagination`, `status` |
| High scores for a game | `GET /retrochain/arcade/v1/highscores/{game_id}` | `Query/GetHighScores` | `game_id`, `limit` |
| Global leaderboard | `GET /retrochain/arcade/v1/leaderboard` | `Query/GetLeaderboard` | `pagination` |
| Player stats | `GET /retrochain/arcade/v1/stats/{player}` | `Query/GetPlayerStats` | `player` |
| Player achievements | `GET /retrochain/arcade/v1/achievements/{player}` | `Query/ListAchievements` | `player`, `pagination` |
| Tournaments | `GET /retrochain/arcade/v1/tournaments` | `Query/ListTournaments` | `pagination`, `status` |
| Tournament by id | `GET /retrochain/arcade/v1/tournaments/{tournament_id}` | `Query/GetTournament` | `tournament_id` |
| Player credits | `GET /retrochain/arcade/v1/credits/{player}` | `Query/GetPlayerCredits` | `player` |

Example (REST):
```bash
curl -s http://localhost:1317/retrochain/arcade/v1/games | jq
```

Example (gRPC):
```bash
grpcurl -plaintext \
  -d '{"player":"cosmos1..."}' \
  localhost:9090 retrochain.arcade.v1.Query/ListPlayerSessions
```

---

## Arcade transaction messages

Broadcast via `retrochaind tx ...` or any Cosmos SDK client. Message types live in `retrochain.arcade.v1.Msg`.

| Message | What it does | Important fields |
|---|---|---|
| `MsgInsertCoin` | Buy credits to play a game. | `creator`, `credits`, `game_id` |
| `MsgStartSession` | Start a new session. | `creator`, `game_id`, `difficulty` |
| `MsgSubmitScore` | Submit score for a session. | `creator`, `session_id`, `score`, `level`, `game_over` |
| `MsgEndSession` | Mark a session finished. | `creator`, `session_id`, `final_score`, `final_level` |
| `MsgUpdateGameScore` | Stream score updates mid-play. | `creator`, `session_id`, `score_delta`, `current_level`, `current_lives` |
| `MsgActivateCombo` | Trigger a combo multiplier. | `creator`, `session_id`, `combo_hits` |
| `MsgUsePowerUp` | Apply a power-up during a session. | `creator`, `session_id`, `power_up_id` |
| `MsgContinueGame` | Continue after game over. | `creator`, `session_id` |
| `MsgClaimAchievement` | Claim an achievement reward. | `creator`, `achievement_id`, `game_id` |
| `MsgSetHighScoreInitials` | Update initials on a high score. | `creator`, `game_id`, `initials` |
| `MsgRegisterGame` | Register a new arcade game (governance/authority gated). | `creator`, `game` |
| `MsgCreateTournament` | Create a tournament. | `creator`, `tournament` |
| `MsgJoinTournament` | Join an existing tournament. | `creator`, `tournament_id` |
| `MsgSubmitTournamentScore` | Post a tournament score. | `creator`, `tournament_id`, `score` |
| `MsgUpdateParams` | Governance-only params update. | `authority`, full `params` object |

Example flow (CLI):
```bash
# Buy two credits and start a session
retrochaind tx arcade insert-coin 2 space-raiders --from alice --gas auto
retrochaind tx arcade start-session space-raiders 3 --from alice --gas auto

# Stream mid-game score and finish
retrochaind tx arcade update-game-score 1 450 2 3 --from alice --gas auto
retrochaind tx arcade submit-score 1 12450 6 true --from alice --gas auto
```

---

## Data shapes (selected)

The arcade module stores the following primary objects (see `genesis.proto` for full details):

- `ArcadeGame`: `game_id`, `name`, `description`, `genre`, `credits_per_play`, `max_players`, `multiplayer_enabled`, `developer`, `release_date`, `active`, `power_ups`, `base_difficulty`.
- `GameSession`: `session_id`, `game_id`, `player`, `credits_used`, `current_score`, `level`, `lives`, `status`, `start_time`, `end_time`, `combo_multiplier`, `power_ups_collected`, `continues_used`.
- `HighScore`: `game_id`, `player`, `score`, `level_reached`, `timestamp`, `initials`, `verified`, `rank`.
- `LeaderboardEntry`: `player`, `total_score`, `games_played`, `achievements_unlocked`, `tournaments_won`, `arcade_tokens`, `rank`, `title`.
- `PlayerAchievement`: `player`, `achievement_id`, `game_id`, `unlocked_at`, `reward_tokens`.
- `Tournament`: `tournament_id`, `name`, `game_id`, `start_time`, `end_time`, `entry_fee`, `prize_pool`, `participants`, `status`, `winner`.
- Params: `base_credits_cost`, `tokens_per_thousand_points`, `max_active_sessions`, `continue_cost_multiplier`, `high_score_reward`, `tournament_registration_fee`, `min_difficulty`, `max_difficulty`, `achievement_reward_multiplier`, `power_up_cost`.

---

## Compatibility and explorer-oriented routes

The API server exposes convenience endpoints to keep explorers working across SDK/CosmWasm versions:

- `/cosmos/tx/v1beta1/txs` accepts `events`/`events[]`; defaults to `query=tx.height>0` if omitted.
- `/arcade/v1/sessions` and `/arcade/v1/achievements`: global lists (bounded scan, capped at 10k items, default limit 5, max 100).
- `/arcade/v1/*` automatically maps to the canonical `/retrochain/arcade/v1/*` gRPC-Gateway routes.
- CosmWasm aliases: `/cosmwasm/wasm/v1/params` -> `/codes/params`; `/codes` -> `/code`; `/contract/{addr}/code-hash` returns stored `code_hash`/`code_id`.
- Smart query helper: POST or GET `/cosmwasm/wasm/v1/contract/{address}/smart` with JSON body, `?query=...`, or `?query_data=<base64>`; it is converted to the canonical gateway path.
- IBC transfer aliases: `/ibc/apps/transfer/v1/denom_traces` (and v1beta1) -> `/denoms`.
- Recent transactions: `/recent-txs` and `/api/recent-txs` proxy to `/cosmos/tx/v1beta1/txs` with `query=tx.height>0` and DESC ordering.
- `/api/*` automatically strips the `/api` prefix to mirror nginx setups that drop it.

---

## Event keys and transaction search

Use `message.sender`, `message.action`, and module-specific attributes when querying transactions. Arcade message actions follow the fully-qualified type, for example:

- `/retrochain.arcade.v1.MsgInsertCoin`
- `/retrochain.arcade.v1.MsgStartSession`
- `/retrochain.arcade.v1.MsgSubmitScore`

Sample search (REST):
```bash
curl -G http://localhost:1317/cosmos/tx/v1beta1/txs \
  --data-urlencode 'query=message.action=\"/retrochain.arcade.v1.MsgInsertCoin\" AND arcade.game_id=\"space-raiders\"' \
  --data-urlencode 'order_by=ORDER_BY_DESC' \
  --data-urlencode 'limit=30'
```

---

## Related assets

- Swagger bundle: `docs/api/swagger.json`
- Arcade proto swagger slices: `proto/retrochain/arcade/v1/*swagger.json`
- Generated TS SDK: `ts-client`
- Custom route implementation: `app/api_routes.go`
