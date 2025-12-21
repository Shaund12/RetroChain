# 🕹️ RetroChain - The Ultimate Cosmos ARCADE Blockchain

**RetroChain** is a revolutionary blockchain built for the **ARCADE GAMING ERA**! Powered by Cosmos SDK and Tendermint, RetroChain brings the nostalgia and excitement of classic arcade gaming into the blockchain world.

## ✨ What Makes RetroChain AMAZING?

### 🕹️ Core Arcade Features
- **🪙 Insert Coin to Play** - Use RETRO tokens to buy credits and play games
- **🏅 High Score Tables** - Classic arcade high score tracking with initials
- **🎲 Multiple Game Genres** - Shooters, Platformers, Puzzle, Fighting, Racing, Beat 'em Up, Maze, and Pinball
- **⚡ Combo System** - Chain hits for massive score multipliers
- **💥 Power-Ups** - Collect and use power-ups during gameplay
- **🔄 Continue System** - Don't give up! Continue your game after Game Over
- **🏆 Achievements** - Unlock achievements and earn bonus RETRO tokens
- **🌐 Global Leaderboards** - Compete with players worldwide
- **🎯 Tournaments** - Join arcade tournaments with prize pools
- **📊 Player Stats** - Track your gaming career with detailed statistics

### 🎮 Arcade Game Library

RetroChain supports multiple classic arcade game genres:

1. **SHOOTER** 🚀 - Space Invaders style games
2. **PLATFORMER** 🦘 - Jump and run classics
3. **PUZZLE** 🧩 - Match-3 and brain teasers
4. **FIGHTING** 🥊 - Head-to-head combat
5. **RACING** 🏎️ - Speed and drift challenges
6. **BEAT 'EM UP** 👊 - Side-scrolling action
7. **MAZE** 🌀 - Pac-Man style navigation
8. **PINBALL** 🎱 - Classic flipper action

### 💰 RETRO Token Economics

- **Token Symbol**: RETRO
- **Base Denom**: uretro (micro-retro)
- **Decimals**: 6
- **Genesis Supply**: Dev template (`config.yml`) is 21,000,000 RETRO; the running network is 100,000,000 RETRO at genesis (see `TOKENOMICS.md`)
- **Use Cases**:
  - Buy arcade credits
  - Purchase power-ups
  - Tournament entry fees
  - Achievement rewards
  - Governance voting

### 🎮 Game Sessions

Start a game session with these features:
- Adjustable difficulty levels (1-10)
- Starting lives based on credits
- Real-time score updates
- Combo multipliers
- Power-up inventory
- Continue system
- Session persistence

### 🏅 Scoring & Rewards

- **Score Points**: Earn points during gameplay
- **Arcade Tokens**: Convert scores to RETRO tokens (configurable ratio)
- **High Score Rewards**: Extra tokens for breaking records
- **Achievement Bonuses**: Multiplied rewards for special accomplishments
- **Tournament Prizes**: Win RETRO from competitive prize pools

## 🚀 Get Started

### Prerequisites
- Go 1.21+
- Ignite CLI

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/retrochain.git
cd retrochain

# Start the blockchain
ignite chain serve
```

### Secrets & local state (important)

This repo intentionally does **not** include any real **mnemonics**, **private keys**, or a canonical mainnet `genesis.json`.

- Generate your own keys locally (e.g. `retrochaind keys add ...`) and keep mnemonics/private keys out of git.
- Node state and key material live under your local home directory (e.g. `$HOME/.retrochaind/`) and should never be committed.
- For running a node (beyond `ignite chain serve`), start with `QUICK_REFERENCE.md` and `PRODUCTION_READINESS.md`.

The `serve` command will:
- Install dependencies
- Build the chain
- Initialize with genesis accounts
- Start the blockchain in development mode

### Default Accounts (dev template)

These accounts are the **local dev template** accounts created by `ignite chain serve` from `config.yml`.
They are **not** the balances/allocations of the running network (`retrochain-mainnet`).

```
👩‍🚀 Alice (Validator)
   - Balance: 10,000,000 RETRO
   - Bonded: 1,000,000 RETRO

👾 Bob (Player)
   - Balance: 5,000,000 RETRO

👨‍💻 Dev (Developer)
   - Balance: 6,000,000 RETRO
```

### Faucet

Get free RETRO tokens for testing (dev/test networks only):
- **Endpoint**: http://0.0.0.0:4500
- **Amount per request**: 10 RETRO
- **Max per address**: 1,000 RETRO
- **Rate limit**: 1 hour

## 🕹️ Playing Games on RetroChain

### 1. Insert Coin (Buy Credits)

```bash
retrochaind tx arcade insert-coin [credits] [game-id] --from alice
```

### 2. Start a Game Session

```bash
retrochaind tx arcade start-session [game-id] [difficulty] --from alice
```

### 3. Play and Update Score

```bash
retrochaind tx arcade update-game-score [session-id] [score-delta] [level] [lives] --from alice
```

### 4. Activate Combo Multiplier

```bash
retrochaind tx arcade activate-combo [session-id] [combo-hits] --from alice
```

### 5. Use Power-Up

```bash
retrochaind tx arcade use-power-up [session-id] [power-up-id] --from alice
```

### 6. Continue After Game Over

```bash
retrochaind tx arcade continue-game [session-id] --from alice
```

### 7. Submit Final Score

```bash
retrochaind tx arcade submit-score [session-id] [score] [level] [game-over] --from alice
```

### 8. Set High Score Initials

```bash
retrochaind tx arcade set-high-score-initials [game-id] "ABC" --from alice
```

## 🔍 Query Commands

### View All Games

```bash
retrochaind query arcade list-games
```

### Check High Scores

```bash
retrochaind query arcade get-high-scores [game-id]
```

### View Global Leaderboard

```bash
retrochaind query arcade get-leaderboard
```

### Check Player Stats

```bash
retrochaind query arcade get-player-stats [player-address]
```

### View Your Sessions

```bash
retrochaind query arcade list-player-sessions [player-address]
```

### Check Your Credits

```bash
retrochaind query arcade get-player-credits [player-address]
```

### View Achievements

```bash
retrochaind query arcade list-achievements [player-address]
```

### List Tournaments

```bash
retrochaind query arcade list-tournaments
```

## 🏆 Tournament System

### Create a Tournament

```bash
retrochaind tx arcade create-tournament \
  --name "Summer Championship" \
  --game-id "space-invaders" \
  --entry-fee 1000000 \
  --prize-pool 10000000 \
  --from dev
```

### Join a Tournament

```bash
retrochaind tx arcade join-tournament [tournament-id] --from alice
```

### Submit Tournament Score

```bash
retrochaind tx arcade submit-tournament-score [tournament-id] [score] --from alice
```

## 🛠️ Development

### Configure

Your blockchain can be configured with `config.yml`. Key settings:

- **Chain ID**: dev template (`config.yml`) is `retrochain-arcade-1`; running network is `retrochain-mainnet`
- **Staking Denom**: uretro
- **Genesis Accounts**: Alice, Bob, Dev
- **API**: http://0.0.0.0:1317
- **gRPC**: http://0.0.0.0:9090
- **gRPC-Web**: http://0.0.0.0:9091

### Web Frontend

Build a Vue.js frontend for your arcade:

```bash
ignite scaffold vue
```

### Register a New Game

Game developers can register new arcade games:

```bash
retrochaind tx arcade register-game \
  --game-id "my-awesome-game" \
  --name "My Awesome Game" \
  --description "The best arcade game ever!" \
  --genre SHOOTER \
  --credits-per-play 1 \
  --from dev
```

### Module Parameters

Arcade module parameters can be updated via governance:

- `base_credits_cost` - Cost per credit in uretro
- `tokens_per_thousand_points` - Reward conversion rate
- `max_active_sessions` - Max concurrent sessions per player
- `continue_cost_multiplier` - Continue price increase percentage
- `high_score_reward` - Bonus tokens for high scores
- `tournament_registration_fee` - Tournament entry cost
- `min_difficulty` / `max_difficulty` - Difficulty range (1-10)
- `achievement_reward_multiplier` - Achievement bonus rate
- `power_up_cost` - Cost to use power-ups

## 📦 Release

Create and push a new version tag:

```bash
git tag v0.1
git push origin v0.1
```

A draft release will be created automatically with build targets.

### Install

Install the latest version:

```bash
curl https://get.ignite.com/username/retrochain@latest! | sudo bash
```

## 🎛️ Arcade Module Features

### Game Session Lifecycle

```
Insert Coin -> Start Session -> Play Game -> Update Score -> 
  🔋 Use Power-Ups
  ⚡ Activate Combos
  🔁 Continue (if Game Over)
  🏁 Submit Final Score -> Check High Score -> End Session
```

### Achievement System

Unlock achievements by:
- Reaching high scores
- Completing levels
- Using combos
- Winning tournaments
- Playing specific games
- Collecting power-ups

### Power-Up System

Collect and use power-ups:
- **Extra Life** - Gain additional lives
- **Score Multiplier** - Temporary score boost
- **Shield** - Protection from damage
- **Time Freeze** - Slow down time
- **Rapid Fire** - Increased attack speed
- **Magnet** - Attract items

## 🌐 Blockchain Explorer Integration

RetroChain is fully compatible with Cosmos blockchain explorers!

### Supported Explorers

- **Mintscan** - Premium Cosmos explorer
- **Big Dipper** - Open-source explorer
- **Ping.pub** - Community explorer
- **ATOMScan** - Cosmos ecosystem explorer

### Explorer Features

? **Transaction Tracking**
- View all transaction details
- Search by hash, address, or block
- Real-time transaction monitoring
- Arcade-specific transaction types

? **Block Information**
- Block height and time
- Transaction count
- Validator information
- Block proposer details

? **Account Details**
- Balance tracking (RETRO tokens)
- Transaction history
- Staking information
- Arcade gaming stats

? **Validator Information**
- Active validator set
- Voting power distribution
- Commission rates
- Uptime tracking

? **Governance Tracking**
- Active proposals
- Voting results
- Proposal history
- Parameter changes

? **Arcade Module**
- Game sessions
- High scores
- Leaderboards
- Tournament results
- Player achievements

### REST API Endpoints

All standard Cosmos SDK REST endpoints are available:

**Base URL:** `http://localhost:1317`

```bash
# Transaction by hash
GET /cosmos/tx/v1beta1/txs/{hash}

# Account info
GET /cosmos/auth/v1beta1/accounts/{address}

# Balances
GET /cosmos/bank/v1beta1/balances/{address}

# Validators
GET /cosmos/staking/v1beta1/validators

# Arcade games
GET /retrochain/arcade/v1/games

# High scores
GET /retrochain/arcade/v1/highscores/{game_id}

# Leaderboard
GET /retrochain/arcade/v1/leaderboard
```

See **[COSMOS_COMMANDS.md](COSMOS_COMMANDS.md)** for complete API documentation.

### Query Transactions

Search transactions by various criteria:

```bash
# By sender
retrochaind query txs --events "message.sender=cosmos1..."

# By action type
retrochaind query txs --events "message.action=/retrochain.arcade.v1.MsgInsertCoin"

# By game
retrochaind query txs --events "arcade.game_id=space-raiders"

# By height
retrochaind query txs --events "tx.height=12345"
```

### WebSocket Subscriptions

Real-time updates via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:26657/websocket');

// Subscribe to new blocks
ws.send(JSON.stringify({
  jsonrpc: '2.0',
  method: 'subscribe',
  params: { query: "tm.event='NewBlock'" }
}));

// Subscribe to arcade events
ws.send(JSON.stringify({
  jsonrpc: '2.0',
  method: 'subscribe',
  params: { query: "arcade.action='high_score'" }
}));
```

### Setting Up Your Own Explorer

Deploy a blockchain explorer for RetroChain:

#### Option 1: Big Dipper

```bash
git clone https://github.com/forbole/big-dipper-2.0-cosmos
cd big-dipper-2.0-cosmos
# Configure for RetroChain
npm install
npm run dev
```

#### Option 2: Ping.pub

```bash
git clone https://github.com/ping-pub/explorer
cd explorer
# Add RetroChain configuration
npm install
npm run serve
```

#### Configuration Example

Add to `chains.config.json`:

```json
{
  "chain_name": "retrochain",
  "api": ["http://localhost:1317"],
  "rpc": ["http://localhost:26657"],
  "sdk_version": "0.50.1",
  "coin_type": "118",
  "min_tx_fee": "5000",
  "addr_prefix": "cosmos",
  "logo": "/logos/retrochain.png",
  "assets": [{
    "base": "uretro",
    "symbol": "RETRO",
    "exponent": "6",
    "coingecko_id": "",
    "logo": "/logos/retro.png"
  }]
}
```

## 📚 Documentation

**[📖 Complete Documentation Index 🧭](DOCUMENTATION_INDEX.md)**

### 🧭 RetroChain Guides

#### Quick Start
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** 🧾 - Essential commands and endpoints (350+ lines)
  - Connection information and endpoints
  - Token details and economics
  - Quick command reference
  - REST API endpoint list
  - Transaction types reference
  - Example workflows

- **[ARCADE_BANNER.txt](ARCADE_BANNER.txt)** 🪩 - ASCII art welcome banner (200+ lines)

#### Core Documentation
- **[README.md](readme.md)** 🧠 - Main documentation (you are here!)
- **[FEATURE_SUMMARY.md](FEATURE_SUMMARY.md)** 🗒️ - Complete feature list (600+ lines)
- **[ARCADE_ENHANCEMENTS.md](ARCADE_ENHANCEMENTS.md)** 🛠️ - Technical enhancements (500+ lines)

#### Player Guides
- **[ARCADE_GUIDE.md](ARCADE_GUIDE.md)** - Comprehensive player's guide (800+ lines)
  - Getting started tutorial
  - Credit and token management
  - Game strategies and tips
  - Tournament participation
  - Achievement hunting
  - Troubleshooting

- **[ARCADE_GAMES.md](ARCADE_GAMES.md)** - Complete game catalog (700+ lines)
  - 8 detailed arcade games
  - 40+ achievements
  - Power-up descriptions
  - Scoring systems
  - Pro tips and strategies

#### Developer Guides
- **[ARCADE_API.md](ARCADE_API.md)** - Developer API reference (1000+ lines)
  - All transaction messages
  - All query endpoints
  - Data type definitions
  - REST, gRPC, WebSocket APIs
  - SDK integration examples (JS/TS, Python, Go)

- **[COSMOS_COMMANDS.md](COSMOS_COMMANDS.md)** - Full Cosmos SDK commands (1500+ lines)
  - Transaction management
  - Query commands
  - Account management
  - Bank, Staking, Governance modules
  - Block and transaction queries
  - Node information
  - Explorer integration

- **[EXPLORER_INTEGRATION.md](EXPLORER_INTEGRATION.md)** - Explorer integration (1200+ lines)
  - Setup instructions for major explorers
  - REST API documentation
  - gRPC service definitions
  - WebSocket events
  - Custom explorer development
  - Example implementations

#### Technical Documentation
- **[ARCADE_ENHANCEMENTS.md](ARCADE_ENHANCEMENTS.md)** - Complete enhancement summary
  - All changes documented
  - Before/after comparison
  - Statistics and metrics
  - Future roadmap

### 🔗 External Resources
- [Ignite CLI Documentation](https://ignite.com/cli)
- [Cosmos SDK Documentation](https://docs.cosmos.network)
- [Tendermint Documentation](https://docs.tendermint.com)
- [Ignite Tutorials](https://docs.ignite.com/guide)
- [CosmJS Documentation](https://cosmos.github.io/cosmjs/)
- [Developer Chat](https://discord.com/invite/ignitecli)

## 💡 Why RetroChain?

RetroChain combines the best of both worlds:

🔗 **Blockchain Technology**
- Decentralized and trustless
- Transparent scoring
- Immutable high score records
- Token-based economy
- Community governance

👾 **Classic Arcade Gaming**
- Nostalgic gameplay
- Competitive leaderboards
- Achievement systems
- Tournament play
- Social gaming

## 🛣️ Roadmap

- 🎯 Core arcade module
- 🏅 High score tracking
- 🏆 Tournament system
- 🏅 Achievement system
- 🖼️ NFT arcade cabinets
- 🔗 Cross-chain gaming
- 🧑‍💻 Game developer SDK
- 📱 Mobile arcade app
- 🥽 VR arcade integration

## 🤝 Contributing

We welcome contributions! RetroChain is built for the community.

## 📜 License

This project is licensed under the Apache License 2.0.

---

**Made with ❤️ and 🕹️ by the RetroChain Team**

*"Insert Coin to Continue..."*
