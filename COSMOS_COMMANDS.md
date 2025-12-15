# ?? RetroChain - Complete Cosmos SDK Command Reference

Essential Cosmos SDK commands for blockchain explorers, wallets, and standard interactions.

## ?? Table of Contents

1. [Transaction Commands](#transaction-commands)
2. [Query Commands](#query-commands)
3. [Account Management](#account-management)
4. [Bank Module](#bank-module)
5. [Staking Module](#staking-module)
6. [Governance Module](#governance-module)
7. [Distribution Module](#distribution-module)
8. [Block & Transaction Queries](#block--transaction-queries)
9. [Node Information](#node-information)
10. [Explorer Integration](#explorer-integration)

---

## ?? Transaction Commands

### View Transaction Details

Get details of any transaction by hash:

```bash
retrochaind query tx [tx-hash]
```

**Example:**
```bash
retrochaind query tx 9F4B2E8A7D3C1B5F6E9A8D7C6B5A4E3D2C1B0A9F8E7D6C5B4A3E2D1C0B9A8F7E
```

**Response:**
```json
{
  "height": "12345",
  "txhash": "9F4B2E8A7D3C1B5F6E9A8D7C6B5A4E3D2C1B0A9F8E7D6C5B4A3E2D1C0B9A8F7E",
  "codespace": "",
  "code": 0,
  "data": "...",
  "raw_log": "...",
  "logs": [...],
  "info": "",
  "gas_wanted": "200000",
  "gas_used": "150000",
  "tx": {...},
  "timestamp": "2024-01-15T12:00:00Z",
  "events": [...]
}
```

### Query Transactions by Events

Search transactions by events:

```bash
# By sender address
retrochaind query txs --events "message.sender=cosmos1..."

# By action
retrochaind query txs --events "message.action=/retrochain.arcade.v1.MsgInsertCoin"

# By game ID
retrochaind query txs --events "arcade.game_id=space-raiders"

# By height
retrochaind query txs --events "tx.height=12345"

# Multiple conditions
retrochaind query txs --events "message.sender=cosmos1... AND message.action=/retrochain.arcade.v1.MsgInsertCoin"
```

**Pagination:**
```bash
retrochaind query txs --events "message.sender=cosmos1..." \
  --page 1 \
  --limit 10
```

### Decode Raw Transaction

Decode a base64-encoded transaction:

```bash
retrochaind tx decode [base64-tx]
```

### Encode Transaction

Encode a transaction to base64:

```bash
retrochaind tx encode [tx-file.json]
```

### Broadcast Transaction

Broadcast a signed transaction:

```bash
# Sync mode (returns immediately)
retrochaind tx broadcast [signed-tx.json] --broadcast-mode sync

# Async mode
retrochaind tx broadcast [signed-tx.json] --broadcast-mode async

# Block mode (waits for inclusion)
retrochaind tx broadcast [signed-tx.json] --broadcast-mode block
```

### Sign Transaction

Sign a transaction offline:

```bash
retrochaind tx sign [unsigned-tx.json] \
  --from alice \
  --chain-id retrochain-mainnet \
  --account-number 0 \
  --sequence 10
```

### Multi-Sign Transaction

Multi-signature transaction workflow:

```bash
# Generate unsigned transaction
retrochaind tx bank send alice bob 1000000uretro \
  --from alice \
  --generate-only > unsigned.json

# Sign by first signer
retrochaind tx sign unsigned.json \
  --from alice \
  --multisig=cosmos1multisig... \
  --chain-id retrochain-mainnet > alice-sig.json

# Sign by second signer
retrochaind tx sign unsigned.json \
  --from bob \
  --multisig=cosmos1multisig... \
  --chain-id retrochain-mainnet > bob-sig.json

# Combine signatures
retrochaind tx multisign unsigned.json cosmos1multisig... \
  alice-sig.json bob-sig.json > signed.json

# Broadcast
retrochaind tx broadcast signed.json
```

---

## ?? Query Commands

### Query Account

Get account information:

```bash
retrochaind query account [address]
```

**Example:**
```bash
retrochaind query account cosmos1abc123...
```

**Response:**
```json
{
  "@type": "/cosmos.auth.v1beta1.BaseAccount",
  "address": "cosmos1abc123...",
  "pub_key": {
    "@type": "/cosmos.crypto.secp256k1.PubKey",
    "key": "A..."
  },
  "account_number": "0",
  "sequence": "10"
}
```

### Query All Accounts

List all accounts:

```bash
retrochaind query auth accounts
```

### Query Balance

Check token balance:

```bash
# All denominations
retrochaind query bank balances [address]

# Specific denomination
retrochaind query bank balances [address] --denom uretro
```

**Example:**
```bash
retrochaind query bank balances cosmos1abc123...
```

**Response:**
```json
{
  "balances": [
    {
      "denom": "uretro",
      "amount": "10000000000000"
    }
  ],
  "pagination": {
    "next_key": null,
    "total": "1"
  }
}
```

### Query Total Supply

Get total token supply:

```bash
# All denominations
retrochaind query bank total

# Specific denomination
retrochaind query bank total --denom uretro
```

### Query Denom Metadata

Get token metadata:

```bash
retrochaind query bank denom-metadata

# Specific denom
retrochaind query bank denom-metadata uretro
```

---

## ?? Account Management

### Create New Account

```bash
retrochaind keys add [account-name]
```

**Options:**
```bash
# From mnemonic
retrochaind keys add alice --recover

# With custom derivation path
retrochaind keys add alice --coin-type 118 --account 0 --index 0

# With keyring backend
retrochaind keys add alice --keyring-backend test
```

### List All Keys

```bash
retrochaind keys list
```

### Show Account Address

```bash
retrochaind keys show [account-name]

# Show address only
retrochaind keys show alice --address

# Show public key
retrochaind keys show alice --pubkey
```

### Export Private Key

```bash
retrochaind keys export alice
```

### Import Private Key

```bash
retrochaind keys import alice private-key.json
```

### Delete Key

```bash
retrochaind keys delete alice
```

### Keyring Backends

```bash
# OS keyring (secure)
retrochaind keys add alice --keyring-backend os

# File-based (encrypted)
retrochaind keys add alice --keyring-backend file

# Test mode (insecure, for development)
retrochaind keys add alice --keyring-backend test

# In-memory (for scripts)
retrochaind keys add alice --keyring-backend memory
```

---

## ?? Bank Module

### Send Tokens

```bash
retrochaind tx bank send [from-address] [to-address] [amount] --from [key-name]
```

**Examples:**
```bash
# Send 100 RETRO
retrochaind tx bank send alice cosmos1bob... 100000000uretro --from alice

# Send to multiple recipients (multi-send)
retrochaind tx bank multi-send alice \
  cosmos1bob...=100000000uretro \
  cosmos1charlie...=50000000uretro \
  --from alice
```

### Query Send Enabled

Check if sending is enabled for a denom:

```bash
retrochaind query bank send-enabled uretro
```

### Query Bank Params

Get bank module parameters:

```bash
retrochaind query bank params
```

---

## ? Staking Module

### Delegate Tokens

Delegate RETRO to a validator:

```bash
retrochaind tx staking delegate [validator-address] [amount] --from [delegator]
```

**Example:**
```bash
retrochaind tx staking delegate cosmosvaloper1... 1000000000000uretro --from alice
```

### Redelegate Tokens

Move delegation from one validator to another:

```bash
retrochaind tx staking redelegate [src-validator] [dst-validator] [amount] --from [delegator]
```

### Unbond Tokens

Start unbonding process:

```bash
retrochaind tx staking unbond [validator-address] [amount] --from [delegator]
```

**Example:**
```bash
retrochaind tx staking unbond cosmosvaloper1... 500000000000uretro --from alice
```

### Query Validators

List all validators:

```bash
# All validators
retrochaind query staking validators

# Active validators only
retrochaind query staking validators --status bonded

# Jailed validators
retrochaind query staking validators --status unbonding
```

### Query Specific Validator

Get validator details:

```bash
retrochaind query staking validator [validator-address]
```

**Response:**
```json
{
  "operator_address": "cosmosvaloper1...",
  "consensus_pubkey": {...},
  "jailed": false,
  "status": "BOND_STATUS_BONDED",
  "tokens": "1000000000000",
  "delegator_shares": "1000000000000.000000000000000000",
  "description": {
    "moniker": "Alice Validator",
    "identity": "",
    "website": "",
    "security_contact": "",
    "details": ""
  },
  "unbonding_height": "0",
  "unbonding_time": "1970-01-01T00:00:00Z",
  "commission": {
    "commission_rates": {
      "rate": "0.100000000000000000",
      "max_rate": "0.200000000000000000",
      "max_change_rate": "0.010000000000000000"
    },
    "update_time": "2024-01-01T00:00:00Z"
  },
  "min_self_delegation": "1"
}
```

### Query Delegations

Get delegations for an address:

```bash
# All delegations
retrochaind query staking delegations [delegator-address]

# Delegation to specific validator
retrochaind query staking delegation [delegator] [validator]
```

### Query Unbonding Delegations

```bash
retrochaind query staking unbonding-delegations [delegator-address]
```

### Query Redelegations

```bash
retrochaind query staking redelegations [delegator-address]
```

### Query Staking Pool

Get total bonded and unbonded tokens:

```bash
retrochaind query staking pool
```

**Response:**
```json
{
  "not_bonded_tokens": "20000000000000",
  "bonded_tokens": "1000000000000"
}
```

### Query Staking Parameters

```bash
retrochaind query staking params
```

**Response:**
```json
{
  "unbonding_time": "1814400s",
  "max_validators": 100,
  "max_entries": 7,
  "historical_entries": 10000,
  "bond_denom": "uretro",
  "min_commission_rate": "0.000000000000000000"
}
```

### Create Validator

Create a new validator:

```bash
retrochaind tx staking create-validator \
  --amount=1000000000000uretro \
  --pubkey=$(retrochaind tendermint show-validator) \
  --moniker="My Validator" \
  --chain-id=retrochain-mainnet \
  --commission-rate="0.10" \
  --commission-max-rate="0.20" \
  --commission-max-change-rate="0.01" \
  --min-self-delegation="1" \
  --from=alice
```

### Edit Validator

Update validator information:

```bash
retrochaind tx staking edit-validator \
  --moniker="New Moniker" \
  --website="https://example.com" \
  --identity="keybase-id" \
  --details="Validator description" \
  --commission-rate="0.05" \
  --from=alice
```

---

## ??? Governance Module

### Submit Proposal

Create a governance proposal:

```bash
# Text proposal
retrochaind tx gov submit-proposal \
  --title="Add New Arcade Game" \
  --description="Proposal to add Galaga clone to RetroChain" \
  --type="Text" \
  --deposit="10000000uretro" \
  --from=dev

# Parameter change proposal
retrochaind tx gov submit-proposal param-change proposal.json --from dev

# Software upgrade proposal
retrochaind tx gov submit-proposal software-upgrade v2.0.0 \
  --title="Upgrade to v2.0.0" \
  --description="Major upgrade" \
  --upgrade-height=100000 \
  --deposit="10000000uretro" \
  --from=dev
```

**Parameter Change Proposal (proposal.json):**
```json
{
  "title": "Increase Max Sessions",
  "description": "Increase max active sessions from 3 to 5",
  "changes": [
    {
      "subspace": "arcade",
      "key": "MaxActiveSessions",
      "value": "5"
    }
  ],
  "deposit": "10000000uretro"
}
```

### Deposit to Proposal

Add deposit to reach minimum:

```bash
retrochaind tx gov deposit [proposal-id] [amount] --from [depositor]
```

**Example:**
```bash
retrochaind tx gov deposit 1 10000000uretro --from alice
```

### Vote on Proposal

Cast your vote:

```bash
retrochaind tx gov vote [proposal-id] [option] --from [voter]
```

**Vote Options:**
- `yes` - Approve the proposal
- `no` - Reject the proposal
- `no_with_veto` - Reject with veto (burns deposits if >33.4%)
- `abstain` - Abstain from voting

**Examples:**
```bash
# Vote yes
retrochaind tx gov vote 1 yes --from alice

# Vote no
retrochaind tx gov vote 1 no --from bob

# Abstain
retrochaind tx gov vote 1 abstain --from charlie
```

### Weighted Vote

Cast weighted vote (multiple options):

```bash
retrochaind tx gov weighted-vote [proposal-id] \
  "yes=0.6,no=0.3,abstain=0.1" \
  --from alice
```

### Query Proposals

List all proposals:

```bash
# All proposals
retrochaind query gov proposals

# By status
retrochaind query gov proposals --status voting_period
retrochaind query gov proposals --status passed
retrochaind query gov proposals --status rejected

# By depositor
retrochaind query gov proposals --depositor cosmos1...

# By voter
retrochaind query gov proposals --voter cosmos1...
```

### Query Specific Proposal

Get proposal details:

```bash
retrochaind query gov proposal [proposal-id]
```

**Response:**
```json
{
  "proposal_id": "1",
  "content": {
    "@type": "/cosmos.gov.v1beta1.TextProposal",
    "title": "Add New Arcade Game",
    "description": "Proposal to add Galaga clone"
  },
  "status": "PROPOSAL_STATUS_VOTING_PERIOD",
  "final_tally_result": {
    "yes": "0",
    "abstain": "0",
    "no": "0",
    "no_with_veto": "0"
  },
  "submit_time": "2024-01-15T12:00:00Z",
  "deposit_end_time": "2024-01-17T12:00:00Z",
  "total_deposit": [
    {
      "denom": "uretro",
      "amount": "100000000"
    }
  ],
  "voting_start_time": "2024-01-15T12:00:00Z",
  "voting_end_time": "2024-01-17T12:00:00Z"
}
```

### Query Deposits

Get proposal deposits:

```bash
# All deposits for proposal
retrochaind query gov deposits [proposal-id]

# Specific depositor
retrochaind query gov deposit [proposal-id] [depositor-address]
```

### Query Votes

Get proposal votes:

```bash
# All votes
retrochaind query gov votes [proposal-id]

# Specific voter
retrochaind query gov vote [proposal-id] [voter-address]
```

### Query Tally

Get current vote tally:

```bash
retrochaind query gov tally [proposal-id]
```

**Response:**
```json
{
  "yes": "5000000000000",
  "abstain": "1000000000000",
  "no": "500000000000",
  "no_with_veto": "0"
}
```

### Query Gov Parameters

Get governance parameters:

```bash
retrochaind query gov params
```

**Response:**
```json
{
  "voting_params": {
    "voting_period": "172800s"
  },
  "tally_params": {
    "quorum": "0.334000000000000000",
    "threshold": "0.500000000000000000",
    "veto_threshold": "0.334000000000000000"
  },
  "deposit_params": {
    "min_deposit": [
      {
        "denom": "uretro",
        "amount": "100000000"
      }
    ],
    "max_deposit_period": "172800s"
  }
}
```

---

## ?? Distribution Module

### Withdraw Rewards

Withdraw staking rewards:

```bash
# From all validators
retrochaind tx distribution withdraw-all-rewards --from alice

# From specific validator
retrochaind tx distribution withdraw-rewards [validator-address] --from alice
```

### Withdraw Commission

Validators withdraw their commission:

```bash
retrochaind tx distribution withdraw-validator-commission [validator-address] --from alice
```

### Set Withdraw Address

Set a different address to receive rewards:

```bash
retrochaind tx distribution set-withdraw-addr [withdraw-address] --from alice
```

### Fund Community Pool

Donate to community pool:

```bash
retrochaind tx distribution fund-community-pool 1000000000uretro --from alice
```

### Query Rewards

Get pending rewards:

```bash
# From all validators
retrochaind query distribution rewards [delegator-address]

# From specific validator
retrochaind query distribution rewards [delegator-address] [validator-address]
```

### Query Commission

Get validator commission:

```bash
retrochaind query distribution commission [validator-address]
```

### Query Community Pool

Get community pool balance:

```bash
retrochaind query distribution community-pool
```

### Query Distribution Parameters

```bash
retrochaind query distribution params
```

---

## ?? Block & Transaction Queries

### Query Latest Block

```bash
retrochaind query block
```

### Query Block by Height

```bash
retrochaind query block [height]
```

**Example:**
```bash
retrochaind query block 12345
```

**Response:**
```json
{
  "block_id": {
    "hash": "...",
    "part_set_header": {...}
  },
  "block": {
    "header": {
      "version": {...},
      "chain_id": "retrochain-mainnet",
      "height": "12345",
      "time": "2024-01-15T12:00:00Z",
      "last_block_id": {...},
      "last_commit_hash": "...",
      "data_hash": "...",
      "validators_hash": "...",
      "next_validators_hash": "...",
      "consensus_hash": "...",
      "app_hash": "...",
      "last_results_hash": "...",
      "evidence_hash": "...",
      "proposer_address": "..."
    },
    "data": {
      "txs": [...]
    },
    "evidence": {...},
    "last_commit": {...}
  }
}
```

### Query Block Results

Get transaction results for a block:

```bash
retrochaind query block-results [height]
```

### Query Latest Block Height

```bash
retrochaind status | jq .SyncInfo.latest_block_height
```

---

## ??? Node Information

### Node Status

Get node status:

```bash
retrochaind status
```

**Response:**
```json
{
  "NodeInfo": {
    "protocol_version": {
      "p2p": "8",
      "block": "11",
      "app": "0"
    },
    "id": "...",
    "listen_addr": "tcp://0.0.0.0:26656",
    "network": "retrochain-mainnet",
    "version": "0.38.0",
    "channels": "...",
    "moniker": "my-node",
    "other": {...}
  },
  "SyncInfo": {
    "latest_block_hash": "...",
    "latest_app_hash": "...",
    "latest_block_height": "12345",
    "latest_block_time": "2024-01-15T12:00:00Z",
    "earliest_block_hash": "...",
    "earliest_app_hash": "...",
    "earliest_block_height": "1",
    "earliest_block_time": "2024-01-01T00:00:00Z",
    "catching_up": false
  },
  "ValidatorInfo": {...}
}
```

### Tendermint Node Info

```bash
retrochaind tendermint show-node-id
retrochaind tendermint show-validator
retrochaind tendermint show-address
```

### Network Info

```bash
retrochaind query tendermint-validator-set
retrochaind query tendermint-validator-set [height]
```

### Peers

```bash
retrochaind tendermint show-node-id
```

---

## ?? Explorer Integration

### Standard REST API Endpoints

**Base URL:** `http://localhost:1317`

#### Transactions
```
GET /cosmos/tx/v1beta1/txs/{hash}
GET /cosmos/tx/v1beta1/txs?events=...
```

#### Blocks
```
GET /cosmos/base/tendermint/v1beta1/blocks/latest
GET /cosmos/base/tendermint/v1beta1/blocks/{height}
```

#### Accounts
```
GET /cosmos/auth/v1beta1/accounts/{address}
GET /cosmos/auth/v1beta1/accounts
```

#### Balances
```
GET /cosmos/bank/v1beta1/balances/{address}
GET /cosmos/bank/v1beta1/supply
GET /cosmos/bank/v1beta1/supply/{denom}
```

#### Staking
```
GET /cosmos/staking/v1beta1/validators
GET /cosmos/staking/v1beta1/validators/{validator_addr}
GET /cosmos/staking/v1beta1/delegations/{delegator_addr}
GET /cosmos/staking/v1beta1/validators/{validator_addr}/delegations
GET /cosmos/staking/v1beta1/delegators/{delegator_addr}/unbonding_delegations
```

#### Governance
```
GET /cosmos/gov/v1beta1/proposals
GET /cosmos/gov/v1beta1/proposals/{proposal_id}
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/votes
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/deposits
GET /cosmos/gov/v1beta1/proposals/{proposal_id}/tally
```

#### Distribution
```
GET /cosmos/distribution/v1beta1/delegators/{delegator_address}/rewards
GET /cosmos/distribution/v1beta1/validators/{validator_address}/commission
GET /cosmos/distribution/v1beta1/community_pool
```

#### Arcade Module (Custom)
```
GET /retrochain/arcade/v1/games
GET /retrochain/arcade/v1/games/{game_id}
GET /retrochain/arcade/v1/highscores/{game_id}
GET /retrochain/arcade/v1/leaderboard
GET /retrochain/arcade/v1/stats/{player}
GET /retrochain/arcade/v1/sessions/{session_id}
GET /retrochain/arcade/v1/tournaments
GET /retrochain/arcade/v1/achievements/{player}
```

### Event Queries for Explorers

Search transactions by module:

```bash
# Bank transfers
retrochaind query txs --events "message.action=/cosmos.bank.v1beta1.MsgSend"

# Staking
retrochaind query txs --events "message.action=/cosmos.staking.v1beta1.MsgDelegate"

# Governance votes
retrochaind query txs --events "message.action=/cosmos.gov.v1beta1.MsgVote"

# Arcade games
retrochaind query txs --events "message.action=/retrochain.arcade.v1.MsgInsertCoin"
retrochaind query txs --events "message.action=/retrochain.arcade.v1.MsgStartSession"
retrochaind query txs --events "message.action=/retrochain.arcade.v1.MsgSubmitScore"
```

### WebSocket Subscriptions

Connect to Tendermint WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:26657/websocket');

// Subscribe to new blocks
ws.send(JSON.stringify({
  jsonrpc: '2.0',
  method: 'subscribe',
  id: 1,
  params: {
    query: "tm.event='NewBlock'"
  }
}));

// Subscribe to new transactions
ws.send(JSON.stringify({
  jsonrpc: '2.0',
  method: 'subscribe',
  id: 2,
  params: {
    query: "tm.event='Tx'"
  }
}));

// Subscribe to arcade events
ws.send(JSON.stringify({
  jsonrpc: '2.0',
  method: 'subscribe',
  id: 3,
  params: {
    query: "arcade.action='high_score'"
  }
}));
```

---

## ?? Transaction Flags

### Common Flags

```bash
--from            # Key name or address
--chain-id        # Chain identifier
--node            # RPC node address (default: tcp://localhost:26657)
--fees            # Fee to pay (e.g., 5000uretro)
--gas             # Gas limit (default: 200000)
--gas-adjustment  # Gas adjustment multiplier (default: 1.0)
--gas-prices      # Gas price (e.g., 0.025uretro)
--dry-run         # Simulate without broadcasting
--generate-only   # Generate unsigned transaction
--offline         # Offline mode
--sign-mode       # Signature mode (direct, amino, textual)
--memo            # Transaction memo
--broadcast-mode  # sync, async, or block
--yes             # Skip confirmation prompt
--output          # Output format (json, text)
```

### Example with All Flags

```bash
retrochaind tx arcade insert-coin 5 space-raiders \
  --from alice \
  --chain-id retrochain-mainnet \
  --node tcp://localhost:26657 \
  --gas auto \
  --gas-adjustment 1.3 \
  --gas-prices 0.025uretro \
  --memo "First game!" \
  --broadcast-mode sync \
  --yes \
  --output json
```

---

## ?? Query Flags

### Common Query Flags

```bash
--height          # Query at specific height
--node            # RPC node address
--output          # Output format (json, text)
--page            # Page number for pagination
--limit           # Results per page
--count-total     # Count total results
```

### Example

```bash
retrochaind query arcade list-games \
  --height 12345 \
  --node tcp://localhost:26657 \
  --output json \
  --page 1 \
  --limit 10 \
  --count-total
```

---

## ?? Explorer-Specific Queries

### Get Chain Info

```bash
# Chain ID
retrochaind status | jq .NodeInfo.network

# Latest height
retrochaind status | jq .SyncInfo.latest_block_height

# Genesis time
retrochaind status | jq .SyncInfo.earliest_block_time
```

### Get Validator Set

```bash
# Current validators
retrochaind query tendermint-validator-set

# At specific height
retrochaind query tendermint-validator-set 12345
```

### Get Inflation

```bash
retrochaind query mint inflation
```

### Get Annual Provisions

```bash
retrochaind query mint annual-provisions
```

### Get Mint Parameters

```bash
retrochaind query mint params
```

---

## ?? Quick Reference

### Most Used Commands

```bash
# Account balance
retrochaind query bank balances [address]

# Send tokens
retrochaind tx bank send [from] [to] [amount] --from [key]

# Transaction details
retrochaind query tx [hash]

# Block details
retrochaind query block [height]

# Validators list
retrochaind query staking validators

# Delegate
retrochaind tx staking delegate [validator] [amount] --from [key]

# Proposals
retrochaind query gov proposals

# Vote
retrochaind tx gov vote [id] [yes/no] --from [key]

# Withdraw rewards
retrochaind tx distribution withdraw-all-rewards --from [key]

# Node status
retrochaind status
```

---

## ?? Additional Resources

- [Cosmos SDK Documentation](https://docs.cosmos.network)
- [Tendermint Documentation](https://docs.tendermint.com)
- [Cosmos REST API](https://cosmos.network/rpc)
- [gRPC Documentation](https://grpc.io/docs/)

---

**Complete Cosmos SDK integration for RetroChain!** ??????

All standard blockchain explorer features fully supported!
