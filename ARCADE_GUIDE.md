# ??? RetroChain Arcade - Player's Guide

Welcome to the RetroChain Arcade! This comprehensive guide will help you become an arcade legend.

## ?? Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding Credits](#understanding-credits)
3. [Playing Games](#playing-games)
4. [Scoring System](#scoring-system)
5. [Power-Ups](#power-ups)
6. [Achievements](#achievements)
7. [Tournaments](#tournaments)
8. [Leaderboards](#leaderboards)
9. [Advanced Strategies](#advanced-strategies)
10. [Troubleshooting](#troubleshooting)

---

## ?? Getting Started

### Step 1: Get RETRO Tokens

You'll need RETRO tokens to play games. You can:

1. **Use the Faucet** (for testing):
   ```bash
   curl -X POST http://0.0.0.0:4500/faucet -d '{"address": "your-address"}'
   ```

2. **Receive from another player**:
   ```bash
   retrochaind tx bank send [sender] [receiver] 1000000uretro --from [sender]
   ```

3. **Buy on an exchange** (when available)

### Step 2: Check Your Balance

```bash
retrochaind query bank balances [your-address]
```

### Step 3: Browse Available Games

```bash
retrochaind query arcade list-games
```

### Step 4: Insert Coin

Choose a game and buy credits:

```bash
retrochaind tx arcade insert-coin 1 space-raiders --from alice
```

### Step 5: Start Playing!

```bash
retrochaind tx arcade start-session space-raiders 5 --from alice
```

---

## ?? Understanding Credits

### What are Credits?

Credits are the currency you use to play arcade games. Think of them like quarters in a real arcade!

### Credit Cost

- Default: 1 credit = configurable amount of uretro (see params)
- Different games may have different credit requirements
- Single-player games: Usually 1 credit
- Multiplayer games: Usually 2 credits

### Buying Credits

```bash
# Buy 1 credit for a specific game
retrochaind tx arcade insert-coin 1 [game-id] --from [your-account]

# Buy 5 credits
retrochaind tx arcade insert-coin 5 [game-id] --from [your-account]
```

### Checking Your Credits

```bash
retrochaind query arcade get-player-credits [your-address]
```

### Credit Management

- Credits don't expire
- You can accumulate credits for later play
- Unused credits stay in your account
- Maximum active sessions: Configurable (default: 3)

---

## ?? Playing Games

### Game Session Lifecycle

```
1. Insert Coin (Buy Credits)
2. Start Session
3. Play Game
4. Update Score (during play)
5. Use Power-Ups (optional)
6. Activate Combos (optional)
7. Continue (if needed)
8. Submit Final Score
9. End Session
```

### Starting a Session

```bash
retrochaind tx arcade start-session [game-id] [difficulty] --from [your-account]
```

Parameters:
- `game-id`: The game you want to play (e.g., "space-raiders")
- `difficulty`: Number from 1 (easy) to 10 (extreme)

Example:
```bash
retrochaind tx arcade start-session space-raiders 5 --from alice
```

Response will include:
- `session_id`: Your unique session ID
- `starting_lives`: Number of lives you have
- `starting_level`: Your starting level

### During Gameplay

#### Update Your Score

```bash
retrochaind tx arcade update-game-score [session-id] [score-delta] [level] [lives] --from [your-account]
```

Example:
```bash
retrochaind tx arcade update-game-score 1 1000 2 3 --from alice
```

#### Activate Combo

When you chain hits together:

```bash
retrochaind tx arcade activate-combo [session-id] [combo-hits] --from [your-account]
```

Example (10-hit combo):
```bash
retrochaind tx arcade activate-combo 1 10 --from alice
```

#### Use a Power-Up

```bash
retrochaind tx arcade use-power-up [session-id] [power-up-id] --from [your-account]
```

Example:
```bash
retrochaind tx arcade use-power-up 1 rapid-fire --from alice
```

### Game Over?

#### Continue

Don't give up! Continue your game:

```bash
retrochaind tx arcade continue-game [session-id] --from [your-account]
```

Cost increases with each continue (configurable multiplier).

### Ending Your Session

#### Submit Final Score

```bash
retrochaind tx arcade submit-score [session-id] [final-score] [level] [is-game-over] --from [your-account]
```

Example:
```bash
retrochaind tx arcade submit-score 1 50000 7 true --from alice
```

Response will show:
- If it's a high score
- Your rank
- Tokens earned
- Achievements unlocked

#### Set Your Initials

If you got a high score, claim your glory:

```bash
retrochaind tx arcade set-high-score-initials [game-id] "ABC" --from alice
```

---

## ?? Scoring System

### How Scoring Works

1. **Base Points**: Each game action awards points
2. **Combo Multipliers**: Chain actions for bonus points
3. **Level Bonuses**: Higher levels = more points
4. **Difficulty Bonuses**: Harder difficulty = higher multiplier

### Combo System

Build combos to multiply your score:

| Combo Hits | Multiplier |
|------------|------------|
| 5          | 2x         |
| 10         | 3x         |
| 20         | 5x         |
| 50         | 10x        |
| 100        | 20x        |

### Score to Token Conversion

- Every 1,000 points = configurable RETRO tokens
- High score bonus: Extra tokens
- Achievement unlock: Bonus tokens
- Tournament prizes: Major tokens

### High Score Table

Each game maintains a top 10 high score table:

```bash
retrochaind query arcade get-high-scores [game-id]
```

Features:
- Player initials (3 letters)
- Score
- Level reached
- Date achieved
- Rank (1-10)
- Verified status

---

## ?? Power-Ups

### Types of Power-Ups

#### Combat Power-Ups
- **Rapid Fire**: Increase attack speed
- **Power Shot**: Extra damage
- **Shield**: Temporary invincibility

#### Utility Power-Ups
- **Extra Life**: Gain a life
- **Time Freeze**: Slow down time
- **Magnet**: Attract collectibles

#### Score Power-Ups
- **2x Multiplier**: Double your score
- **3x Multiplier**: Triple your score
- **5x Multiplier**: Quintuple your score

### Getting Power-Ups

Power-ups can be:
1. Collected during gameplay
2. Purchased with arcade tokens
3. Unlocked via achievements

### Using Power-Ups

```bash
retrochaind tx arcade use-power-up [session-id] [power-up-id] --from [your-account]
```

Available power-up IDs:
- `rapid-fire`
- `shield`
- `extra-life`
- `time-freeze`
- `magnet`
- `score-2x`
- `score-3x`
- `power-shot`

### Power-Up Strategy

1. **Save for boss fights**: Don't waste on easy sections
2. **Combine power-ups**: Some stack for greater effect
3. **Time your usage**: Use at optimal moments
4. **Know the duration**: Most last 10-30 seconds

---

## ??? Achievements

### Achievement Categories

#### Rookie (5-10 tokens)
- Complete tutorials
- Play first games
- Basic milestones

#### Advanced (10-50 tokens)
- High scores
- Multiple games
- Tournaments

#### Expert (50-100 tokens)
- Top leaderboard
- Win tournaments
- Master specific games

#### Master (100-500 tokens)
- Ultimate challenges
- Complete collections
- Legendary status

### Claiming Achievements

When you unlock an achievement:

```bash
retrochaind tx arcade claim-achievement [achievement-id] [game-id] --from [your-account]
```

Example:
```bash
retrochaind tx arcade claim-achievement first-blood space-raiders --from alice
```

### Viewing Your Achievements

```bash
retrochaind query arcade list-achievements [your-address]
```

### Achievement Benefits

1. **Tokens**: Earn RETRO tokens
2. **Titles**: Unlock special titles
3. **Leaderboard**: Boost your rank
4. **Bragging Rights**: Show off to friends

---

## ?? Tournaments

### What are Tournaments?

Competitive events where players battle for prizes!

### Finding Tournaments

```bash
retrochaind query arcade list-tournaments
```

Filter by status:
- `REGISTRATION`: Sign-ups open
- `ACTIVE`: Currently running
- `COMPLETED`: Finished
- `CANCELLED`: Cancelled

### Creating a Tournament

Game developers and community leaders can create tournaments:

```bash
retrochaind tx arcade create-tournament \
  --name "Summer Championship" \
  --game-id "space-raiders" \
  --entry-fee 1000000 \
  --prize-pool 10000000 \
  --start-time "2024-06-01T00:00:00Z" \
  --end-time "2024-06-30T23:59:59Z" \
  --from dev
```

### Joining a Tournament

```bash
retrochaind tx arcade join-tournament [tournament-id] --from [your-account]
```

Requirements:
- Pay entry fee
- Meet eligibility requirements
- During registration period

### Playing in a Tournament

1. Join the tournament
2. Play the tournament game
3. Submit your best score:

```bash
retrochaind tx arcade submit-tournament-score [tournament-id] [score] --from [your-account]
```

### Tournament Rules

- **One best score** counts per player
- **No continues** in most tournaments
- **Time limits** apply
- **Verified scores** only
- **Fair play** enforced

### Prizes

Tournament prizes are distributed:
- 1st Place: 50% of prize pool
- 2nd Place: 30% of prize pool
- 3rd Place: 20% of prize pool

(Distribution can vary by tournament)

### Viewing Tournament

```bash
retrochaind query arcade get-tournament [tournament-id]
```

Shows:
- Current standings
- Prize pool
- Time remaining
- Your rank
- Top players

---

## ?? Leaderboards

### Global Leaderboard

The ultimate measure of arcade mastery:

```bash
retrochaind query arcade get-leaderboard
```

Ranking factors:
- Total score across all games
- Games played
- Achievements unlocked
- Tournaments won
- Arcade tokens earned

### Player Stats

Check any player's statistics:

```bash
retrochaind query arcade get-player-stats [player-address]
```

Stats include:
- Global rank
- Total score
- Games played
- Achievements
- Tournaments won
- Favorite games
- Credits spent

### Your Stats

```bash
retrochaind query arcade get-player-stats $(retrochaind keys show alice -a)
```

### Game-Specific Leaderboards

Each game has its own high score table:

```bash
retrochaind query arcade get-high-scores [game-id]
```

### Climbing the Ranks

Tips to improve your rank:
1. Play diverse games
2. Unlock achievements
3. Win tournaments
4. Maintain high scores
5. Play consistently

---

## ?? Advanced Strategies

### Maximizing Tokens

1. **High scores** - Get on leaderboards
2. **Achievements** - Complete challenges
3. **Tournaments** - Win competitions
4. **Combos** - Build massive multipliers
5. **Daily play** - Consistent rewards

### Credit Management

1. **Buy in bulk** - Plan your sessions
2. **Choose difficulty wisely** - Higher risk, higher reward
3. **Master one game first** - Become expert before diversifying
4. **Save for tournaments** - Big prizes require entry fees

### Combo Mastery

1. **Learn patterns** - Enemies spawn predictably
2. **Stay focused** - One hit breaks the combo
3. **Position carefully** - Be ready for next target
4. **Use power-ups** - Extend combo windows

### Tournament Strategy

1. **Practice first** - Know the game inside out
2. **Time your runs** - Play when you're sharp
3. **Watch the leaders** - Learn from the best
4. **Stress management** - Stay calm under pressure
5. **Risk vs. Reward** - Know when to play safe

### Achievement Hunting

1. **Check requirements** - Know what you need
2. **Plan your path** - Efficient unlocking
3. **Stack achievements** - Get multiple in one run
4. **Track progress** - Know what's close
5. **Complete sets** - Full game achievements for bonuses

---

## ?? Troubleshooting

### Common Issues

#### "Insufficient credits"
- **Solution**: Buy more credits with `insert-coin`
- **Check balance**: `get-player-credits [address]`

#### "Session not found"
- **Cause**: Session ended or invalid ID
- **Solution**: Start a new session

#### "Maximum active sessions reached"
- **Cause**: Too many open sessions
- **Solution**: End inactive sessions first

#### "Transaction failed"
- **Check**: Account has enough RETRO tokens
- **Check**: Valid session ID
- **Check**: Correct parameters

### Getting Help

1. **Check documentation**: Read this guide
2. **Query on-chain state**: Use query commands
3. **Community**: Join Discord/Telegram
4. **Support**: Contact RetroChain team

### Best Practices

1. **Start with easy difficulty** - Learn the game
2. **Practice regularly** - Build skills
3. **Manage your bankroll** - Don't spend all credits at once
4. **Join community** - Learn from others
5. **Have fun!** - It's a game, enjoy it

---

## ?? Quick Reference

### Essential Commands

```bash
# Buy credits
retrochaind tx arcade insert-coin [credits] [game-id] --from [account]

# Start game
retrochaind tx arcade start-session [game-id] [difficulty] --from [account]

# Update score
retrochaind tx arcade update-game-score [session-id] [score] [level] [lives] --from [account]

# Use power-up
retrochaind tx arcade use-power-up [session-id] [power-up-id] --from [account]

# Continue
retrochaind tx arcade continue-game [session-id] --from [account]

# Submit score
retrochaind tx arcade submit-score [session-id] [score] [level] [game-over] --from [account]

# Check high scores
retrochaind query arcade get-high-scores [game-id]

# Check leaderboard
retrochaind query arcade get-leaderboard

# Check your stats
retrochaind query arcade get-player-stats [address]
```

---

## ?? Tips from the Pros

### From the Top Players

> "Master one game completely before moving to the next. Depth beats breadth."  
> — **ACE**, Global Rank #1

> "Save your power-ups for when you really need them. A shield during a boss fight is worth 10 shields on easy levels."  
> — **REX**, Tournament Champion

> "Build your combos slowly at first. Rushing leads to mistakes."  
> — **ZEN**, Combo Master

> "Join tournaments even if you think you can't win. The experience is invaluable."  
> — **PRO**, Tournament Veteran

> "Check the leaderboard daily. Study what the top players are doing."  
> — **MAX**, Leaderboard Analyst

---

## ?? Conclusion

You now have everything you need to dominate the RetroChain Arcade! Remember:

1. **Practice makes perfect** - Keep playing
2. **Learn from mistakes** - Every game over is a lesson
3. **Community matters** - Help others, learn together
4. **Have fun** - That's what it's all about!

**Ready to become a legend? Insert your coin now!** ???

---

For more information:
- [Game Catalog](ARCADE_GAMES.md)
- [Main README](readme.md)
- [Cosmos SDK Docs](https://docs.cosmos.network)

**Good luck, and may your combos be infinite!** ?????
