# ?? RetroChain Quick Reference Card

Essential commands and endpoints for developers and blockchain explorers.

---

## ?? Connection Information

These are the **default local dev** addresses. For a remote/public network, replace with your RPC/REST endpoints.

| Service | Address | Description |
|---------|---------|-------------|
| RPC | `http://localhost:26657` | Tendermint RPC |
| REST API | `http://localhost:1317` | Cosmos REST API |
| gRPC | `localhost:9090` | gRPC endpoint |
| gRPC-Web | `http://localhost:9091` | gRPC-Web endpoint |
| WebSocket | `ws://localhost:26657/websocket` | Real-time events |
| Faucet | `http://localhost:4500` | Test token faucet (dev/test networks only) |

---

## ?? Token Information

| Property | Value |
|----------|-------|
| Symbol | RETRO |
| Base Denom | uretro |
| Decimals | 6 |
| Chain ID | Running network: `retrochain-mainnet`; Dev template (`config.yml`): `retrochain-arcade-1` |
| Address Prefix | cosmos |
| Genesis Supply | Dev template (`config.yml`): 21,000,000 RETRO; Running network: 100,000,000 RETRO (see `TOKENOMICS.md`) |
| 1 RETRO | 1,000,000 uretro |

---

## ? Quick Commands

### Essential Queries

```bash
# Node status
retrochaind status

# Account balance
retrochaind query bank balances [address]

# Transaction by hash
retrochaind query tx [hash]

# Latest block
retrochaind query block

# All validators
retrochaind query staking validators

# All arcade games
retrochaind query arcade list-games

# High scores
retrochaind query arcade get-high-scores [game-id]

# Global leaderboard
retrochaind query arcade get-leaderboard
```

### Essential Transactions

```bash
# Send tokens
retrochaind tx bank send [from] [to] [amount]uretro --from [key]

# Delegate tokens
retrochaind tx staking delegate [validator] [amount]uretro --from [key]

# Vote on proposal
retrochaind tx gov vote [proposal-id] yes --from [key]

# Insert coin (buy credits)
retrochaind tx arcade insert-coin [credits] [game-id] --from [key]

# Start game session
retrochaind tx arcade start-session [game-id] [difficulty] --from [key]

# Submit score
retrochaind tx arcade submit-score [session-id] [score] [level] true --from [key]
```

---

## ?? REST API Endpoints

### Core Endpoints

```
GET  /cosmos/base/tendermint/v1beta1/node_info
GET  /cosmos/base/tendermint/v1beta1/syncing
GET  /cosmos/base/tendermint/v1beta1/blocks/latest
GET  /cosmos/base/tendermint/v1beta1/blocks/{height}
GET  /cosmos/tx/v1beta1/txs/{hash}
GET  /cosmos/tx/v1beta1/txs?events=...
GET  /cosmos/auth/v1beta1/accounts/{address}
GET  /cosmos/bank/v1beta1/balances/{address}
GET  /cosmos/staking/v1beta1/validators
GET  /cosmos/gov/v1beta1/proposals
```

### Arcade Endpoints

```
GET  /retrochain/arcade/v1/games
GET  /retrochain/arcade/v1/games/{game_id}
GET  /retrochain/arcade/v1/highscores/{game_id}
GET  /retrochain/arcade/v1/leaderboard
GET  /retrochain/arcade/v1/stats/{player}
GET  /retrochain/arcade/v1/sessions/{session_id}
GET  /retrochain/arcade/v1/tournaments
GET  /retrochain/arcade/v1/achievements/{player}
GET  /retrochain/arcade/v1/credits/{player}
GET  /retrochain/arcade/v1/params
```

---

## ?? Arcade Transaction Types

| Type | Description |
|------|-------------|
| `MsgInsertCoin` | Buy game credits |
| `MsgStartSession` | Start a game |
| `MsgUpdateGameScore` | Update score during play |
| `MsgSubmitScore` | Submit final score |
| `MsgActivateCombo` | Trigger combo multiplier |
| `MsgUsePowerUp` | Use a power-up |
| `MsgContinueGame` | Continue after game over |
| `MsgSetHighScoreInitials` | Set high score initials |
| `MsgRegisterGame` | Register new game |
| `MsgCreateTournament` | Create tournament |
| `MsgJoinTournament` | Join tournament |
| `MsgSubmitTournamentScore` | Submit tournament score |
| `MsgClaimAchievement` | Claim achievement reward |

---

## ?? Transaction Search Queries

```bash
# By sender
--events "message.sender=cosmos1..."

# By action type
--events "message.action=/retrochain.arcade.v1.MsgInsertCoin"

# By game ID
--events "arcade.game_id=space-raiders"

# By height
--events "tx.height=12345"

# Multiple conditions
--events "message.sender=cosmos1... AND arcade.game_id=space-raiders"
```

---

## ?? Genesis Games

| Game ID | Name | Genre | Credits | Max Players |
|---------|------|-------|---------|-------------|
| `space-raiders` | Space Raiders | Shooter | 1 | 1 |
| `platform-hero` | Platform Hero | Platformer | 1 | 1 |
| `puzzle-panic` | Puzzle Panic | Puzzle | 1 | 1 |
| `street-brawler` | Street Brawler | Fighting | 2 | 2 |
| `turbo-racer` | Turbo Racer | Racing | 2 | 4 |

---

## ?? Power-Ups

| ID | Name | Type | Effect |
|----|------|------|--------|
| `rapid-fire` | Rapid Fire | Combat | Increase attack speed |
| `shield` | Shield | Combat | Temporary invincibility |
| `extra-life` | Extra Life | Utility | Gain additional life |
| `time-freeze` | Time Freeze | Utility | Slow down time |
| `magnet` | Magnet | Utility | Attract collectibles |
| `score-2x` | 2x Multiplier | Score | Double score |
| `score-3x` | 3x Multiplier | Score | Triple score |
| `power-shot` | Power Shot | Combat | Increased damage |

---

## ?? Combo Multipliers

| Hits | Multiplier |
|------|------------|
| 5 | 2x |
| 10 | 3x |
| 20 | 5x |
| 50 | 10x |
| 100 | 20x |

---

## ?? Module Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `base_credits_cost` | 1000000 | Cost per credit (uretro) |
| `tokens_per_thousand_points` | 1 | Tokens earned per 1K points |
| `max_active_sessions` | 3 | Max concurrent sessions |
| `continue_cost_multiplier` | 150 | Continue cost increase (%) |
| `high_score_reward` | 100 | Bonus for high scores |
| `tournament_registration_fee` | 10000000 | Tournament entry fee |
| `min_difficulty` | 1 | Minimum difficulty |
| `max_difficulty` | 10 | Maximum difficulty |
| `achievement_reward_multiplier` | 2 | Achievement bonus multiplier |
| `power_up_cost` | 5 | Power-up cost (tokens) |

---

## ?? Account Management

```bash
# Create new account
retrochaind keys add [name]

# List accounts
retrochaind keys list

# Show address
retrochaind keys show [name] --address

# Export key
retrochaind keys export [name]

# Import key
retrochaind keys import [name] [file]

# Delete key
retrochaind keys delete [name]
```

---

## ?? Genesis Accounts

| Name | Role | Balance | Bonded |
|------|------|---------|--------|
| Alice | Validator & Top Player | 10,000,000 RETRO | 1,000,000 RETRO |
| Bob | Challenger | 5,000,000 RETRO | - |
| Dev | Game Master | 6,000,000 RETRO | - |

---

## ?? WebSocket Event Subscriptions

```javascript
// New blocks
{ query: "tm.event='NewBlock'" }

// Transactions
{ query: "tm.event='Tx'" }

// High scores
{ query: "arcade.action='high_score'" }

// Game started
{ query: "arcade.action='game_started'" }

// Tournament joined
{ query: "arcade.action='tournament_joined'" }

// Achievement unlocked
{ query: "arcade.action='achievement_unlocked'" }
```

---

## ??? Common Transaction Flags

```bash
--from            # Signer key name
--chain-id        # retrochain-mainnet
--gas             # Gas limit (or 'auto')
--gas-adjustment  # 1.3 (for auto gas)
--gas-prices      # 0.025uretro
--fees            # Alternative to gas-prices
--memo            # Transaction memo
--broadcast-mode  # sync, async, or block
--yes             # Skip confirmation
--output          # json or text
```

---

## ?? Common Query Flags

```bash
--height          # Query at height
--output          # json or text
--page            # Page number
--limit           # Results per page
--count-total     # Count results
```

---

## ?? Example Game Flow

```bash
# 1. Buy 5 credits for Space Raiders
retrochaind tx arcade insert-coin 5 space-raiders --from alice

# 2. Start a game session (difficulty 5)
retrochaind tx arcade start-session space-raiders 5 --from alice
# Returns: session_id=1

# 3. Play game and update score
retrochaind tx arcade update-game-score 1 5000 2 3 --from alice

# 4. Activate combo (10 hits)
retrochaind tx arcade activate-combo 1 10 --from alice

# 5. Use power-up
retrochaind tx arcade use-power-up 1 rapid-fire --from alice

# 6. Game over? Continue!
retrochaind tx arcade continue-game 1 --from alice

# 7. Submit final score
retrochaind tx arcade submit-score 1 50000 7 true --from alice

# 8. Set your initials
retrochaind tx arcade set-high-score-initials space-raiders "ACE" --from alice

# 9. Check leaderboard
retrochaind query arcade get-high-scores space-raiders
```

---

## ?? Important Links

| Resource | URL |
|----------|-----|
| Documentation | [README.md](readme.md) |
| Game Catalog | [ARCADE_GAMES.md](ARCADE_GAMES.md) |
| Player Guide | [ARCADE_GUIDE.md](ARCADE_GUIDE.md) |
| API Reference | [ARCADE_API.md](ARCADE_API.md) |
| Cosmos Commands | [COSMOS_COMMANDS.md](COSMOS_COMMANDS.md) |
| Explorer Setup | [EXPLORER_INTEGRATION.md](EXPLORER_INTEGRATION.md) |

---

## ?? Pro Tips

1. **Gas Estimation**: Always use `--gas auto --gas-adjustment 1.3`
2. **Batch Operations**: Combine multiple operations in one transaction
3. **Event Monitoring**: Use WebSocket for real-time updates
4. **Pagination**: Always paginate large result sets
5. **Error Handling**: Check `code` field in transaction response
6. **Testing**: Use `--dry-run` to simulate without broadcasting
7. **Offline Signing**: Use `--generate-only` for offline transactions
8. **Explorer Integration**: Provide chain ID and RPC endpoints

---

## ?? Achievement Quick List

**Rookie** (5-10 tokens):
- First Game, First Win, Coin Collector, Quick Start

**Advanced** (10-50 tokens):
- Multi-Genre Master, High Scorer, Tournament Player, Power User

**Expert** (50-100 tokens):
- Arcade Legend, Tournament Champion, Complete Collection

**Master** (100-500 tokens):
- RetroChain Master, Ultimate Champion, Top of the World, Arcade Mogul

---

## ?? Support

- **Documentation**: See all `.md` files in repository
- **Discord**: [Ignite CLI Discord](https://discord.com/invite/ignitecli)
- **GitHub**: Create issues for bugs or feature requests
- **Community**: Join Cosmos SDK forums

---

**Quick Reference Version 1.0** | Last Updated: 2024

??? **RetroChain - Where Blockchain Meets Classic Arcade Gaming** ??
