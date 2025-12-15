# ??? RetroChain Arcade - API Reference

Complete API reference for integrating with the RetroChain Arcade blockchain.

## ?? Table of Contents

1. [Transaction Messages](#transaction-messages)
2. [Query Endpoints](#query-endpoints)
3. [Data Types](#data-types)
4. [REST API](#rest-api)
5. [gRPC API](#grpc-api)
6. [WebSocket Events](#websocket-events)
7. [SDK Integration](#sdk-integration)

---

## ?? Transaction Messages

### MsgInsertCoin

Buy credits to play arcade games.

**CLI Command:**
```bash
retrochaind tx arcade insert-coin [credits] [game-id] --from [account]
```

**Proto Definition:**
```protobuf
message MsgInsertCoin {
  string creator = 1;
  uint64 credits = 2;
  string game_id = 3;
}
```

**Parameters:**
- `creator` - Player's blockchain address
- `credits` - Number of credits to purchase
- `game_id` - ID of the game to play

**Response:**
```protobuf
message MsgInsertCoinResponse {
  uint64 total_credits = 1;
  string tokens_spent = 2;
}
```

**Example:**
```bash
retrochaind tx arcade insert-coin 5 space-raiders \
  --from alice \
  --chain-id retrochain-mainnet \
  --gas auto \
  --gas-adjustment 1.3
```

---

### MsgStartSession

Start a new game session.

**CLI Command:**
```bash
retrochaind tx arcade start-session [game-id] [difficulty] --from [account]
```

**Proto Definition:**
```protobuf
message MsgStartSession {
  string creator = 1;
  string game_id = 2;
  uint64 difficulty = 3;
}
```

**Parameters:**
- `creator` - Player's blockchain address
- `game_id` - Game to play
- `difficulty` - Difficulty level (1-10)

**Response:**
```protobuf
message MsgStartSessionResponse {
  uint64 session_id = 1;
  uint64 starting_lives = 2;
  uint64 starting_level = 3;
}
```

---

### MsgUpdateGameScore

Update score during gameplay.

**CLI Command:**
```bash
retrochaind tx arcade update-game-score [session-id] [score-delta] [level] [lives] --from [account]
```

**Proto Definition:**
```protobuf
message MsgUpdateGameScore {
  string creator = 1;
  uint64 session_id = 2;
  uint64 score_delta = 3;
  uint64 current_level = 4;
  uint64 current_lives = 5;
}
```

---

### MsgActivateCombo

Activate combo multiplier.

**CLI Command:**
```bash
retrochaind tx arcade activate-combo [session-id] [combo-hits] --from [account]
```

**Proto Definition:**
```protobuf
message MsgActivateCombo {
  string creator = 1;
  uint64 session_id = 2;
  uint64 combo_hits = 3;
}
```

**Response:**
```protobuf
message MsgActivateComboResponse {
  uint64 multiplier = 1;
  uint64 bonus_score = 2;
}
```

---

### MsgUsePowerUp

Use a power-up during gameplay.

**CLI Command:**
```bash
retrochaind tx arcade use-power-up [session-id] [power-up-id] --from [account]
```

**Proto Definition:**
```protobuf
message MsgUsePowerUp {
  string creator = 1;
  uint64 session_id = 2;
  string power_up_id = 3;
}
```

**Available Power-Up IDs:**
- `rapid-fire` - Increase attack speed
- `shield` - Temporary invincibility
- `extra-life` - Gain additional life
- `time-freeze` - Slow down time
- `magnet` - Attract collectibles
- `score-2x` - Double score
- `score-3x` - Triple score
- `power-shot` - Increased damage

---

### MsgContinueGame

Continue playing after game over.

**CLI Command:**
```bash
retrochaind tx arcade continue-game [session-id] --from [account]
```

**Proto Definition:**
```protobuf
message MsgContinueGame {
  string creator = 1;
  uint64 session_id = 2;
}
```

**Response:**
```protobuf
message MsgContinueGameResponse {
  uint64 continues_remaining = 1;
  uint64 lives_granted = 2;
  string cost = 3;
}
```

---

### MsgSubmitScore

Submit final score and end game.

**CLI Command:**
```bash
retrochaind tx arcade submit-score [session-id] [score] [level] [game-over] --from [account]
```

**Proto Definition:**
```protobuf
message MsgSubmitScore {
  string creator = 1;
  uint64 session_id = 2;
  uint64 score = 3;
  uint64 level = 4;
  bool game_over = 5;
}
```

**Response:**
```protobuf
message MsgSubmitScoreResponse {
  bool is_high_score = 1;
  uint64 rank = 2;
  uint64 tokens_earned = 3;
  repeated string achievements_unlocked = 4;
}
```

---

### MsgSetHighScoreInitials

Set your initials for high score table.

**CLI Command:**
```bash
retrochaind tx arcade set-high-score-initials [game-id] [initials] --from [account]
```

**Proto Definition:**
```protobuf
message MsgSetHighScoreInitials {
  string creator = 1;
  string game_id = 2;
  string initials = 3;
}
```

**Rules:**
- Exactly 3 characters
- A-Z only
- Case insensitive

---

### MsgRegisterGame

Register a new arcade game (developers only).

**CLI Command:**
```bash
retrochaind tx arcade register-game [game-json] --from [developer]
```

**Proto Definition:**
```protobuf
message MsgRegisterGame {
  string creator = 1;
  ArcadeGame game = 2;
}
```

---

### MsgCreateTournament

Create a new tournament.

**CLI Command:**
```bash
retrochaind tx arcade create-tournament [tournament-json] --from [organizer]
```

**Proto Definition:**
```protobuf
message MsgCreateTournament {
  string creator = 1;
  Tournament tournament = 2;
}
```

---

### MsgJoinTournament

Join an existing tournament.

**CLI Command:**
```bash
retrochaind tx arcade join-tournament [tournament-id] --from [player]
```

**Proto Definition:**
```protobuf
message MsgJoinTournament {
  string creator = 1;
  string tournament_id = 2;
}
```

---

### MsgSubmitTournamentScore

Submit score for tournament.

**CLI Command:**
```bash
retrochaind tx arcade submit-tournament-score [tournament-id] [score] --from [player]
```

**Proto Definition:**
```protobuf
message MsgSubmitTournamentScore {
  string creator = 1;
  string tournament_id = 2;
  uint64 score = 3;
}
```

---

### MsgClaimAchievement

Claim achievement reward.

**CLI Command:**
```bash
retrochaind tx arcade claim-achievement [achievement-id] [game-id] --from [player]
```

**Proto Definition:**
```protobuf
message MsgClaimAchievement {
  string creator = 1;
  string achievement_id = 2;
  string game_id = 3;
}
```

---

## ?? Query Endpoints

### List Games

Get all registered arcade games.

**CLI Command:**
```bash
retrochaind query arcade list-games
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/games
```

**Query Parameters:**
- `pagination.limit` - Number of results per page
- `pagination.offset` - Offset for pagination
- `genre` - Filter by game genre (optional)
- `active_only` - Show only active games (boolean)

**Response:**
```json
{
  "games": [
    {
      "game_id": "space-raiders",
      "name": "Space Raiders",
      "description": "Classic space shooter",
      "genre": "GENRE_SHOOTER",
      "credits_per_play": 1,
      "max_players": 1,
      "multiplayer_enabled": false,
      "developer": "RetroChain Studios",
      "release_date": "2024-01-01T00:00:00Z",
      "active": true,
      "power_ups": ["rapid-fire", "shield", "score-2x"],
      "base_difficulty": 5
    }
  ],
  "pagination": {
    "next_key": null,
    "total": "5"
  }
}
```

---

### Get Game

Get details of a specific game.

**CLI Command:**
```bash
retrochaind query arcade get-game [game-id]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/games/{game_id}
```

---

### Get High Scores

Get high scores for a game.

**CLI Command:**
```bash
retrochaind query arcade get-high-scores [game-id] [limit]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/highscores/{game_id}?limit=10
```

**Response:**
```json
{
  "scores": [
    {
      "game_id": "space-raiders",
      "player": "cosmos1...",
      "score": 150000,
      "level_reached": 10,
      "timestamp": "2024-01-15T12:00:00Z",
      "initials": "ACE",
      "verified": true,
      "rank": 1
    }
  ]
}
```

---

### Get Leaderboard

Get global leaderboard.

**CLI Command:**
```bash
retrochaind query arcade get-leaderboard
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/leaderboard
```

**Response:**
```json
{
  "entries": [
    {
      "player": "cosmos1...",
      "total_score": 5000000,
      "games_played": 150,
      "achievements_unlocked": 42,
      "tournaments_won": 5,
      "arcade_tokens": 10000,
      "rank": 1,
      "title": "Arcade Legend"
    }
  ],
  "pagination": {
    "next_key": null,
    "total": "100"
  }
}
```

---

### Get Player Stats

Get statistics for a specific player.

**CLI Command:**
```bash
retrochaind query arcade get-player-stats [player-address]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/stats/{player}
```

**Response:**
```json
{
  "stats": {
    "player": "cosmos1...",
    "total_score": 5000000,
    "games_played": 150,
    "achievements_unlocked": 42,
    "tournaments_won": 5,
    "arcade_tokens": 10000,
    "rank": 1,
    "title": "Arcade Master"
  },
  "total_credits_spent": 200,
  "active_sessions": 1,
  "favorite_games": ["space-raiders", "platform-hero"]
}
```

---

### Get Session

Get details of a game session.

**CLI Command:**
```bash
retrochaind query arcade get-session [session-id]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/sessions/{session_id}
```

**Response:**
```json
{
  "session": {
    "session_id": 12345,
    "game_id": "space-raiders",
    "player": "cosmos1...",
    "credits_used": 2,
    "current_score": 45000,
    "level": 5,
    "lives": 3,
    "status": "STATUS_ACTIVE",
    "start_time": "2024-01-15T12:00:00Z",
    "end_time": null,
    "combo_multiplier": 5,
    "power_ups_collected": ["rapid-fire", "shield"],
    "continues_used": 1
  }
}
```

---

### List Player Sessions

Get all sessions for a player.

**CLI Command:**
```bash
retrochaind query arcade list-player-sessions [player-address]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/sessions/player/{player}
```

**Query Parameters:**
- `status` - Filter by session status (optional)
- `pagination.limit` - Results per page

---

### List Achievements

Get player's achievements.

**CLI Command:**
```bash
retrochaind query arcade list-achievements [player-address]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/achievements/{player}
```

**Response:**
```json
{
  "achievements": [
    {
      "player": "cosmos1...",
      "achievement_id": "first-blood",
      "game_id": "space-raiders",
      "unlocked_at": "2024-01-15T12:00:00Z",
      "reward_tokens": 100
    }
  ],
  "pagination": {
    "next_key": null,
    "total": "15"
  }
}
```

---

### List Tournaments

Get all tournaments.

**CLI Command:**
```bash
retrochaind query arcade list-tournaments
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/tournaments
```

**Query Parameters:**
- `status` - Filter by tournament status

---

### Get Tournament

Get tournament details.

**CLI Command:**
```bash
retrochaind query arcade get-tournament [tournament-id]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/tournaments/{tournament_id}
```

**Response:**
```json
{
  "tournament": {
    "tournament_id": "summer-championship-2024",
    "name": "Summer Championship 2024",
    "game_id": "space-raiders",
    "start_time": "2024-06-01T00:00:00Z",
    "end_time": "2024-06-30T23:59:59Z",
    "entry_fee": 1000000,
    "prize_pool": 10000000,
    "participants": [
      {
        "player": "cosmos1...",
        "best_score": 150000,
        "rank": 1,
        "qualified": true
      }
    ],
    "status": "TOURNAMENT_ACTIVE",
    "winner": null
  }
}
```

---

### Get Player Credits

Get player's available credits.

**CLI Command:**
```bash
retrochaind query arcade get-player-credits [player-address]
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/credits/{player}
```

**Response:**
```json
{
  "credits": 10,
  "arcade_tokens": 500
}
```

---

### Get Params

Get arcade module parameters.

**CLI Command:**
```bash
retrochaind query arcade params
```

**REST Endpoint:**
```
GET /retrochain/arcade/v1/params
```

**Response:**
```json
{
  "params": {
    "base_credits_cost": "1000000",
    "tokens_per_thousand_points": 1,
    "max_active_sessions": 3,
    "continue_cost_multiplier": 150,
    "high_score_reward": 100,
    "tournament_registration_fee": "10000000",
    "min_difficulty": 1,
    "max_difficulty": 10,
    "achievement_reward_multiplier": 2,
    "power_up_cost": 5
  }
}
```

---

## ?? Data Types

### ArcadeGame

```protobuf
message ArcadeGame {
  string game_id = 1;
  string name = 2;
  string description = 3;
  GameGenre genre = 4;
  uint64 credits_per_play = 5;
  uint64 max_players = 6;
  bool multiplayer_enabled = 7;
  string developer = 8;
  google.protobuf.Timestamp release_date = 9;
  bool active = 10;
  repeated string power_ups = 11;
  uint64 base_difficulty = 12;
}
```

### GameGenre

```protobuf
enum GameGenre {
  GENRE_UNSPECIFIED = 0;
  GENRE_SHOOTER = 1;
  GENRE_PLATFORMER = 2;
  GENRE_PUZZLE = 3;
  GENRE_FIGHTING = 4;
  GENRE_RACING = 5;
  GENRE_BEAT_EM_UP = 6;
  GENRE_MAZE = 7;
  GENRE_PINBALL = 8;
}
```

### GameSession

```protobuf
message GameSession {
  uint64 session_id = 1;
  string game_id = 2;
  string player = 3;
  uint64 credits_used = 4;
  uint64 current_score = 5;
  uint64 level = 6;
  uint64 lives = 7;
  SessionStatus status = 8;
  google.protobuf.Timestamp start_time = 9;
  google.protobuf.Timestamp end_time = 10;
  uint64 combo_multiplier = 11;
  repeated string power_ups_collected = 12;
  uint64 continues_used = 13;
}
```

### SessionStatus

```protobuf
enum SessionStatus {
  STATUS_UNSPECIFIED = 0;
  STATUS_ACTIVE = 1;
  STATUS_PAUSED = 2;
  STATUS_COMPLETED = 3;
  STATUS_GAME_OVER = 4;
}
```

### HighScore

```protobuf
message HighScore {
  string game_id = 1;
  string player = 2;
  uint64 score = 3;
  uint64 level_reached = 4;
  google.protobuf.Timestamp timestamp = 5;
  string initials = 6;
  bool verified = 7;
  uint64 rank = 8;
}
```

### LeaderboardEntry

```protobuf
message LeaderboardEntry {
  string player = 1;
  uint64 total_score = 2;
  uint64 games_played = 3;
  uint64 achievements_unlocked = 4;
  uint64 tournaments_won = 5;
  uint64 arcade_tokens = 6;
  uint64 rank = 7;
  string title = 8;
}
```

### Tournament

```protobuf
message Tournament {
  string tournament_id = 1;
  string name = 2;
  string game_id = 3;
  google.protobuf.Timestamp start_time = 4;
  google.protobuf.Timestamp end_time = 5;
  uint64 entry_fee = 6;
  uint64 prize_pool = 7;
  repeated TournamentParticipant participants = 8;
  TournamentStatus status = 9;
  string winner = 10;
}
```

---

## ?? REST API

### Base URL

```
http://localhost:1317
```

### Authentication

Most endpoints don't require authentication for querying.  
Transaction endpoints require signed transactions.

### Headers

```
Content-Type: application/json
Accept: application/json
```

### Error Responses

```json
{
  "code": 5,
  "message": "insufficient credits",
  "details": []
}
```

---

## ?? gRPC API

### Connection

```
localhost:9090
```

### Service Definition

```protobuf
service Msg {
  rpc InsertCoin(MsgInsertCoin) returns (MsgInsertCoinResponse);
  rpc StartSession(MsgStartSession) returns (MsgStartSessionResponse);
  // ... other RPCs
}

service Query {
  rpc ListGames(QueryListGamesRequest) returns (QueryListGamesResponse);
  rpc GetHighScores(QueryGetHighScoresRequest) returns (QueryGetHighScoresResponse);
  // ... other queries
}
```

### Go Client Example

```go
import (
    "context"
    "google.golang.org/grpc"
    arcadetypes "retrochain/x/arcade/types"
)

func main() {
    conn, _ := grpc.Dial("localhost:9090", grpc.WithInsecure())
    defer conn.Close()
    
    client := arcadetypes.NewQueryClient(conn)
    
    res, err := client.ListGames(context.Background(), &arcadetypes.QueryListGamesRequest{
        ActiveOnly: true,
    })
    
    // Handle response
}
```

---

## ?? WebSocket Events

### Subscribe to Events

```javascript
const ws = new WebSocket('ws://localhost:26657/websocket');

ws.send(JSON.stringify({
  jsonrpc: '2.0',
  method: 'subscribe',
  id: 1,
  params: {
    query: "tm.event='Tx' AND arcade.action='high_score'"
  }
}));
```

### Event Types

- `arcade.game_started` - New game session started
- `arcade.score_updated` - Score updated
- `arcade.high_score` - New high score achieved
- `arcade.achievement_unlocked` - Achievement unlocked
- `arcade.tournament_joined` - Player joined tournament
- `arcade.combo_activated` - Combo multiplier activated

---

## ??? SDK Integration

### JavaScript/TypeScript

```typescript
import { SigningStargateClient } from '@cosmjs/stargate';
import { DirectSecp256k1HdWallet } from '@cosmjs/proto-signing';

const mnemonic = "your mnemonic here";
const wallet = await DirectSecp256k1HdWallet.fromMnemonic(mnemonic);
const [account] = await wallet.getAccounts();

const client = await SigningStargateClient.connectWithSigner(
  "http://localhost:26657",
  wallet
);

// Insert coin
const msg = {
  typeUrl: "/retrochain.arcade.v1.MsgInsertCoin",
  value: {
    creator: account.address,
    credits: 5,
    gameId: "space-raiders"
  }
};

const result = await client.signAndBroadcast(
  account.address,
  [msg],
  "auto"
);
```

### Python

```python
from cosmospy import BIP32DerivationError, Transaction

# Create transaction
tx = Transaction(
    privkey="your_private_key",
    account_num=0,
    sequence=0,
    fee=1000,
    gas=200000,
    memo="",
  chain_id="retrochain-mainnet",
    sync_mode="sync",
)

# Insert coin message
msg = {
    "type": "arcade/MsgInsertCoin",
    "value": {
        "creator": "cosmos1...",
        "credits": 5,
        "game_id": "space-raiders"
    }
}

tx.add_transfer(msg)
pushable_tx = tx.get_pushable()
```

---

## ?? Best Practices

### Rate Limiting

- Maximum 10 requests per second per IP
- Burst limit: 20 requests

### Pagination

Always use pagination for large result sets:

```bash
retrochaind query arcade list-games \
  --limit 10 \
  --offset 0
```

### Error Handling

Always check transaction results:

```javascript
if (result.code !== 0) {
  console.error("Transaction failed:", result.rawLog);
}
```

### Gas Estimation

Use automatic gas estimation:

```bash
--gas auto --gas-adjustment 1.3
```

---

## ?? Additional Resources

- [Cosmos SDK Documentation](https://docs.cosmos.network)
- [gRPC Documentation](https://grpc.io/docs/)
- [CosmJS Documentation](https://cosmos.github.io/cosmjs/)
- [RetroChain Main README](readme.md)
- [Arcade Player Guide](ARCADE_GUIDE.md)
- [Game Catalog](ARCADE_GAMES.md)

---

**Happy Building! May your integrations be bug-free and your games be epic!** ????
