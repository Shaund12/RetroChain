# ?? RetroChain Explorer Integration Guide

Complete guide for integrating RetroChain with blockchain explorers and building custom explorer interfaces.

## ?? Table of Contents

1. [Overview](#overview)
2. [Standard Cosmos Modules](#standard-cosmos-modules)
3. [Custom Arcade Module](#custom-arcade-module)
4. [Setting Up Explorers](#setting-up-explorers)
5. [API Endpoints](#api-endpoints)
6. [WebSocket Events](#websocket-events)
7. [Custom Explorer Development](#custom-explorer-development)
8. [Example Implementations](#example-implementations)

---

## ?? Overview

RetroChain is fully compatible with standard Cosmos blockchain explorers and includes custom arcade gaming features.

### Supported Features

? **Standard Cosmos SDK**
- Transactions and blocks
- Accounts and balances
- Validators and staking
- Governance proposals
- Distribution and rewards
- IBC transfers

? **Arcade Module (Custom)**
- Game sessions
- High score tables
- Global leaderboards
- Tournament tracking
- Player statistics
- Achievement systems

---

## ?? Standard Cosmos Modules

### Available Modules

RetroChain includes all standard Cosmos SDK modules:

1. **auth** - Account authentication
2. **bank** - Token transfers
3. **staking** - Validator delegation
4. **distribution** - Staking rewards
5. **gov** - Governance proposals
6. **slashing** - Validator penalties
7. **mint** - Token minting
8. **upgrade** - Chain upgrades
9. **authz** - Authorization grants
10. **feegrant** - Fee allowances
11. **crisis** - Invariant checks
12. **evidence** - Byzantine behavior
13. **params** - Parameter management
14. **vesting** - Token vesting

### Module Endpoints

Each module exposes REST and gRPC endpoints:

```
/cosmos/auth/v1beta1/*
/cosmos/bank/v1beta1/*
/cosmos/staking/v1beta1/*
/cosmos/distribution/v1beta1/*
/cosmos/gov/v1beta1/*
/cosmos/slashing/v1beta1/*
/cosmos/mint/v1beta1/*
/cosmos/upgrade/v1beta1/*
```

---

## ?? Custom Arcade Module

### Arcade Endpoints

RetroChain's custom arcade module provides gaming-specific endpoints:

```
/retrochain/arcade/v1/games
/retrochain/arcade/v1/games/{game_id}
/retrochain/arcade/v1/highscores/{game_id}
/retrochain/arcade/v1/leaderboard
/retrochain/arcade/v1/stats/{player}
/retrochain/arcade/v1/sessions/{session_id}
/retrochain/arcade/v1/sessions/player/{player}
/retrochain/arcade/v1/achievements/{player}
/retrochain/arcade/v1/tournaments
/retrochain/arcade/v1/tournaments/{tournament_id}
/retrochain/arcade/v1/credits/{player}
/retrochain/arcade/v1/params
```

### Transaction Types

Custom arcade transactions:

- `MsgInsertCoin` - Buy game credits
- `MsgStartSession` - Start game
- `MsgUpdateGameScore` - Update score
- `MsgSubmitScore` - Submit final score
- `MsgActivateCombo` - Activate combo
- `MsgUsePowerUp` - Use power-up
- `MsgContinueGame` - Continue after game over
- `MsgSetHighScoreInitials` - Set initials
- `MsgRegisterGame` - Register new game
- `MsgCreateTournament` - Create tournament
- `MsgJoinTournament` - Join tournament
- `MsgSubmitTournamentScore` - Submit tournament score
- `MsgClaimAchievement` - Claim achievement

### Event Types

Custom events emitted:

- `arcade.game_started` - New session started
- `arcade.score_updated` - Score changed
- `arcade.high_score` - High score achieved
- `arcade.combo_activated` - Combo triggered
- `arcade.power_up_used` - Power-up activated
- `arcade.game_continued` - Continue used
- `arcade.achievement_unlocked` - Achievement earned
- `arcade.tournament_joined` - Joined tournament
- `arcade.game_registered` - New game added

---

## ??? Setting Up Explorers

### Option 1: Mintscan

**Commercial explorer with premium features**

Contact Cosmostation for integration:
- Website: https://www.mintscan.io
- Email: contact@cosmostation.io

Provide:
- Chain ID: `retrochain-arcade-1`
- RPC: Your RPC endpoint
- REST: Your REST API endpoint
- Token info: RETRO (uretro)

### Option 2: Big Dipper

**Open-source explorer**

```bash
# Clone repository
git clone https://github.com/forbole/big-dipper-2.0-cosmos
cd big-dipper-2.0-cosmos

# Install dependencies
npm install

# Configure for RetroChain
cp .env.example .env
```

**Configuration (.env):**
```env
NEXT_PUBLIC_CHAIN_ID=retrochain-arcade-1
NEXT_PUBLIC_CHAIN_NAME=RetroChain
NEXT_PUBLIC_RPC_ENDPOINT=http://localhost:26657
NEXT_PUBLIC_API_ENDPOINT=http://localhost:1317
NEXT_PUBLIC_WEBSOCKET_ENDPOINT=ws://localhost:26657/websocket
NEXT_PUBLIC_COIN_MINIMAL_DENOM=uretro
NEXT_PUBLIC_COIN_EXPONENT=6
NEXT_PUBLIC_COIN_DISPLAY_DENOM=RETRO
```

```bash
# Run development server
npm run dev

# Build for production
npm run build
npm run start
```

### Option 3: Ping.pub

**Community-driven explorer**

```bash
# Clone repository
git clone https://github.com/ping-pub/explorer
cd explorer

# Install dependencies
npm install
```

**Add Chain Configuration (src/chains/mainnet/retrochain.json):**
```json
{
  "chain_name": "retrochain",
  "api": ["http://localhost:1317"],
  "rpc": ["http://localhost:26657"],
  "snapshot_provider": "",
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

```bash
# Run development server
npm run serve

# Build for production
npm run build
```

### Option 4: ATOMScan

**Cosmos ecosystem explorer**

Contact ATOMScan team:
- Website: https://atomscan.com
- GitHub: https://github.com/atomscan

Provide chain configuration and custom module details.

---

## ?? API Endpoints

### REST API

**Base URL:** `http://localhost:1317`

#### Core Endpoints

```bash
# Node info
GET /cosmos/base/tendermint/v1beta1/node_info

# Syncing status
GET /cosmos/base/tendermint/v1beta1/syncing

# Latest block
GET /cosmos/base/tendermint/v1beta1/blocks/latest

# Block by height
GET /cosmos/base/tendermint/v1beta1/blocks/{height}

# Validator set
GET /cosmos/base/tendermint/v1beta1/validatorsets/latest
GET /cosmos/base/tendermint/v1beta1/validatorsets/{height}
```

#### Transaction Endpoints

```bash
# Get transaction by hash
GET /cosmos/tx/v1beta1/txs/{hash}

# Search transactions
GET /cosmos/tx/v1beta1/txs?events=message.sender='{address}'

# Simulate transaction
POST /cosmos/tx/v1beta1/simulate

# Broadcast transaction
POST /cosmos/tx/v1beta1/txs
```

#### Account Endpoints

```bash
# Get account
GET /cosmos/auth/v1beta1/accounts/{address}

# Get all accounts
GET /cosmos/auth/v1beta1/accounts

# Module accounts
GET /cosmos/auth/v1beta1/module_accounts
```

#### Bank Endpoints

```bash
# Get balances
GET /cosmos/bank/v1beta1/balances/{address}

# Get balance by denom
GET /cosmos/bank/v1beta1/balances/{address}/by_denom?denom=uretro

# Total supply
GET /cosmos/bank/v1beta1/supply

# Supply by denom
GET /cosmos/bank/v1beta1/supply/by_denom?denom=uretro

# Denom metadata
GET /cosmos/bank/v1beta1/denoms_metadata
GET /cosmos/bank/v1beta1/denoms_metadata/{denom}
```

#### Staking Endpoints

```bash
# All validators
GET /cosmos/staking/v1beta1/validators

# Validator by address
GET /cosmos/staking/v1beta1/validators/{validator_addr}

# Delegations to validator
GET /cosmos/staking/v1beta1/validators/{validator_addr}/delegations

# Delegator delegations
GET /cosmos/staking/v1beta1/delegations/{delegator_addr}

# Delegation
GET /cosmos/staking/v1beta1/validators/{validator_addr}/delegations/{delegator_addr}

# Unbonding delegations
GET /cosmos/staking/v1beta1/delegators/{delegator_addr}/unbonding_delegations

# Redelegations
GET /cosmos/staking/v1beta1/delegators/{delegator_addr}/redelegations

# Staking pool
GET /cosmos/staking/v1beta1/pool

# Staking parameters
GET /cosmos/staking/v1beta1/params
```

#### Governance Endpoints

```bash
# All proposals
GET /cosmos/gov/v1beta1/proposals

# Proposal by ID
GET /cosmos/gov/v1beta1/proposals/{proposal_id}

# Deposits
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/deposits

# Specific deposit
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/deposits/{depositor}

# Votes
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/votes

# Specific vote
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/votes/{voter}

# Tally
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/tally

# Gov parameters
GET /cosmos/gov/v1beta1/params/{params_type}
```

#### Distribution Endpoints

```bash
# Delegation rewards
GET /cosmos/distribution/v1beta1/delegators/{delegator_address}/rewards

# Rewards from validator
GET /cosmos/distribution/v1beta1/delegators/{delegator_address}/rewards/{validator_address}

# Validator commission
GET /cosmos/distribution/v1beta1/validators/{validator_address}/commission

# Validator slashes
GET /cosmos/distribution/v1beta1/validators/{validator_address}/slashes

# Community pool
GET /cosmos/distribution/v1beta1/community_pool

# Distribution parameters
GET /cosmos/distribution/v1beta1/params
```

#### Arcade Endpoints (Custom)

```bash
# All games
GET /retrochain/arcade/v1/games

# Specific game
GET /retrochain/arcade/v1/games/{game_id}

# High scores
GET /retrochain/arcade/v1/highscores/{game_id}?limit=10

# Global leaderboard
GET /retrochain/arcade/v1/leaderboard

# Player stats
GET /retrochain/arcade/v1/stats/{player}

# Game session
GET /retrochain/arcade/v1/sessions/{session_id}

# Player sessions
GET /retrochain/arcade/v1/sessions/player/{player}

# Player achievements
GET /retrochain/arcade/v1/achievements/{player}

# All tournaments
GET /retrochain/arcade/v1/tournaments

# Specific tournament
GET /retrochain/arcade/v1/tournaments/{tournament_id}

# Player credits
GET /retrochain/arcade/v1/credits/{player}

# Arcade parameters
GET /retrochain/arcade/v1/params
```

### gRPC API

**Address:** `localhost:9090`

#### Service Definitions

```protobuf
// Standard Cosmos services
cosmos.tx.v1beta1.Service
cosmos.auth.v1beta1.Query
cosmos.bank.v1beta1.Query
cosmos.staking.v1beta1.Query
cosmos.distribution.v1beta1.Query
cosmos.gov.v1beta1.Query

// Arcade custom services
retrochain.arcade.v1.Query
retrochain.arcade.v1.Msg
```

#### Example gRPC Client (Go)

```go
package main

import (
    "context"
    "fmt"
    "google.golang.org/grpc"
    banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
    arcadetypes "retrochain/x/arcade/types"
)

func main() {
    // Connect to gRPC
    conn, err := grpc.Dial(
        "localhost:9090",
        grpc.WithInsecure(),
    )
    if err != nil {
        panic(err)
    }
    defer conn.Close()
    
    // Bank query client
    bankClient := banktypes.NewQueryClient(conn)
    
    // Query balance
    balRes, err := bankClient.Balance(context.Background(), &banktypes.QueryBalanceRequest{
        Address: "cosmos1...",
        Denom:   "uretro",
    })
    if err != nil {
        panic(err)
    }
    fmt.Printf("Balance: %s\n", balRes.Balance.Amount)
    
    // Arcade query client
    arcadeClient := arcadetypes.NewQueryClient(conn)
    
    // Query games
    gamesRes, err := arcadeClient.ListGames(context.Background(), &arcadetypes.QueryListGamesRequest{
        ActiveOnly: true,
    })
    if err != nil {
        panic(err)
    }
    
    for _, game := range gamesRes.Games {
        fmt.Printf("Game: %s - %s\n", game.GameId, game.Name)
    }
}
```

---

## ?? WebSocket Events

### Tendermint WebSocket

**Address:** `ws://localhost:26657/websocket`

#### Subscribe to Events

```javascript
const WebSocket = require('ws');
const ws = new WebSocket('ws://localhost:26657/websocket');

ws.on('open', () => {
  // Subscribe to new blocks
  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'subscribe',
    id: 1,
    params: {
      query: "tm.event='NewBlock'"
    }
  }));
  
  // Subscribe to transactions
  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'subscribe',
    id: 2,
    params: {
      query: "tm.event='Tx'"
    }
  }));
  
  // Subscribe to arcade high scores
  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'subscribe',
    id: 3,
    params: {
      query: "arcade.action='high_score'"
    }
  }));
});

ws.on('message', (data) => {
  const event = JSON.parse(data);
  console.log('Event:', event);
});
```

#### Available Event Queries

```javascript
// Block events
"tm.event='NewBlock'"
"tm.event='NewBlockHeader'"

// Transaction events
"tm.event='Tx'"
"tm.event='Tx' AND tx.height=12345"

// Message events
"message.action='/cosmos.bank.v1beta1.MsgSend'"
"message.sender='cosmos1...'"

// Arcade events
"arcade.action='game_started'"
"arcade.action='high_score'"
"arcade.action='tournament_joined'"
"arcade.game_id='space-raiders'"
"arcade.player='cosmos1...'"
```

---

## ?? Custom Explorer Development

### Tech Stack Options

#### Option 1: React + CosmJS

```bash
npx create-react-app retrochain-explorer
cd retrochain-explorer
npm install @cosmjs/stargate @cosmjs/proto-signing
```

**Example Component:**
```typescript
import { StargateClient } from '@cosmjs/stargate';
import { useEffect, useState } from 'react';

function LatestBlocks() {
  const [blocks, setBlocks] = useState([]);
  
  useEffect(() => {
    const client = await StargateClient.connect('http://localhost:26657');
    
    const fetchBlocks = async () => {
      const height = await client.getHeight();
      const blockList = [];
      
      for (let i = height; i > height - 10; i--) {
        const block = await client.getBlock(i);
        blockList.push(block);
      }
      
      setBlocks(blockList);
    };
    
    fetchBlocks();
  }, []);
  
  return (
    <div>
      <h2>Latest Blocks</h2>
      {blocks.map(block => (
        <div key={block.header.height}>
          Block #{block.header.height} - {block.txs.length} txs
        </div>
      ))}
    </div>
  );
}
```

#### Option 2: Vue + Cosmos SDK REST

```bash
vue create retrochain-explorer
cd retrochain-explorer
npm install axios
```

**Example Component:**
```vue
<template>
  <div>
    <h2>High Scores - {{ gameId }}</h2>
    <table>
      <tr v-for="score in highScores" :key="score.rank">
        <td>{{ score.rank }}</td>
        <td>{{ score.initials }}</td>
        <td>{{ score.score }}</td>
      </tr>
    </table>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      gameId: 'space-raiders',
      highScores: []
    };
  },
  async mounted() {
    const res = await axios.get(
      `http://localhost:1317/retrochain/arcade/v1/highscores/${this.gameId}`
    );
    this.highScores = res.data.scores;
  }
};
</script>
```

#### Option 3: Next.js + GraphQL

```bash
npx create-next-app retrochain-explorer
cd retrochain-explorer
npm install @apollo/client graphql
```

Use Cosmos GraphQL endpoints or build custom GraphQL server.

### Key Features to Implement

1. **Dashboard**
   - Latest blocks
   - Recent transactions
   - Active validators
   - Network stats
   - Arcade leaderboard

2. **Blocks**
   - Block list
   - Block details
   - Transaction list per block
   - Validator info

3. **Transactions**
   - Transaction search
   - Transaction details
   - Event logs
   - Message decoding

4. **Accounts**
   - Balance display
   - Transaction history
   - Delegation info
   - Gaming stats

5. **Validators**
   - Validator list
   - Validator details
   - Delegation info
   - Commission rates

6. **Governance**
   - Proposal list
   - Proposal details
   - Voting results
   - Deposit tracking

7. **Arcade** (Custom)
   - Game library
   - High score tables
   - Global leaderboard
   - Tournament results
   - Player profiles
   - Achievement showcase

---

## ?? Example Implementations

### Transaction Decoder

```javascript
async function decodeTransaction(txHash) {
  const response = await fetch(
    `http://localhost:1317/cosmos/tx/v1beta1/txs/${txHash}`
  );
  const data = await response.json();
  
  return {
    hash: data.tx_response.txhash,
    height: data.tx_response.height,
    timestamp: data.tx_response.timestamp,
    fee: data.tx.auth_info.fee.amount,
    gasUsed: data.tx_response.gas_used,
    gasWanted: data.tx_response.gas_wanted,
    messages: data.tx.body.messages.map(msg => ({
      type: msg['@type'],
      ...msg
    })),
    events: data.tx_response.events
  };
}
```

### High Score Display

```javascript
async function getHighScores(gameId, limit = 10) {
  const response = await fetch(
    `http://localhost:1317/retrochain/arcade/v1/highscores/${gameId}?limit=${limit}`
  );
  const data = await response.json();
  
  return data.scores.map((score, index) => ({
    rank: index + 1,
    initials: score.initials,
    score: score.score,
    level: score.level_reached,
    player: score.player,
    timestamp: new Date(score.timestamp).toLocaleDateString()
  }));
}
```

### Live Block Feed

```javascript
const ws = new WebSocket('ws://localhost:26657/websocket');

ws.onopen = () => {
  ws.send(JSON.stringify({
    jsonrpc: '2.0',
    method: 'subscribe',
    id: 1,
    params: { query: "tm.event='NewBlock'" }
  }));
};

ws.onmessage = async (event) => {
  const data = JSON.parse(event.data);
  
  if (data.result?.data?.value?.block) {
    const block = data.result.data.value.block;
    
    console.log({
      height: block.header.height,
      time: block.header.time,
      txCount: block.data.txs?.length || 0,
      proposer: block.header.proposer_address
    });
  }
};
```

---

## ?? Resources

- [Cosmos REST API](https://cosmos.network/rpc)
- [CosmJS Documentation](https://cosmos.github.io/cosmjs/)
- [Tendermint RPC](https://docs.tendermint.com/v0.34/rpc/)
- [Big Dipper GitHub](https://github.com/forbole/big-dipper-2.0-cosmos)
- [Ping.pub GitHub](https://github.com/ping-pub/explorer)

---

**Complete explorer integration for RetroChain!** ???

All data accessible for blockchain explorers and custom interfaces!
