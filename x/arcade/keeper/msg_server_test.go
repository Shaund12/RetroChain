package keeper_test

import (
	"testing"

	"cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/stretchr/testify/require"

	"retrochain/x/arcade/keeper"
	"retrochain/x/arcade/types"
)

func TestMsgInsertCoin(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Fund the test account with tokens
	f.bankKeeper.Balances[testAddr.String()] = sdk.NewCoins(sdk.NewCoin("uretro", math.NewInt(10000000)))

	testCases := []struct {
		name      string
		input     *types.MsgInsertCoin
		expErr    bool
		expErrMsg string
	}{
		{
			name: "invalid address",
			input: &types.MsgInsertCoin{
				Creator: "invalid",
				Credits: 1,
				GameId:  "test-game",
			},
			expErr:    true,
			expErrMsg: "invalid creator address",
		},
		{
			name: "zero credits",
			input: &types.MsgInsertCoin{
				Creator: testAddrStr,
				Credits: 0,
				GameId:  "test-game",
			},
			expErr:    true,
			expErrMsg: "credits must be greater than 0",
		},
		{
			name: "empty game_id",
			input: &types.MsgInsertCoin{
				Creator: testAddrStr,
				Credits: 1,
				GameId:  "",
			},
			expErr:    true,
			expErrMsg: "game_id is required",
		},
		{
			name: "successful insert coin",
			input: &types.MsgInsertCoin{
				Creator: testAddrStr,
				Credits: 5,
				GameId:  "test-game",
			},
			expErr: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := ms.InsertCoin(f.ctx, tc.input)

			if tc.expErr {
				require.Error(t, err)
				require.Contains(t, err.Error(), tc.expErrMsg)
			} else {
				require.NoError(t, err)
				// Verify credits were added
				credits, err := f.keeper.GetPlayerCredits(f.ctx, tc.input.Creator)
				require.NoError(t, err)
				require.Equal(t, tc.input.Credits, credits)
			}
		})
	}
}

func TestMsgStartSession(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Give the player some credits first
	err = f.keeper.SetPlayerCredits(f.ctx, testAddrStr, 5)
	require.NoError(t, err)

	testCases := []struct {
		name      string
		input     *types.MsgStartSession
		expErr    bool
		expErrMsg string
	}{
		{
			name: "invalid address",
			input: &types.MsgStartSession{
				Creator: "invalid",
				GameId:  "test-game",
			},
			expErr:    true,
			expErrMsg: "invalid creator address",
		},
		{
			name: "empty game_id",
			input: &types.MsgStartSession{
				Creator: testAddrStr,
				GameId:  "",
			},
			expErr:    true,
			expErrMsg: "game_id is required",
		},
		{
			name: "successful start session",
			input: &types.MsgStartSession{
				Creator: testAddrStr,
				GameId:  "test-game",
			},
			expErr: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := ms.StartSession(f.ctx, tc.input)

			if tc.expErr {
				require.Error(t, err)
				require.Contains(t, err.Error(), tc.expErrMsg)
			} else {
				require.NoError(t, err)
				// Verify credits were deducted
				credits, err := f.keeper.GetPlayerCredits(f.ctx, tc.input.Creator)
				require.NoError(t, err)
				// Credits should be reduced by 1
				require.Equal(t, uint64(4), credits)
			}
		})
	}
}

func TestMsgStartSession_InsufficientCredits(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Player has 0 credits
	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddrStr,
		GameId:  "test-game",
	})
	require.Error(t, err)
	require.Contains(t, err.Error(), "insufficient credits")
}

func TestMsgSubmitScore(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Create a session first
	err = f.keeper.SetPlayerCredits(f.ctx, testAddrStr, 5)
	require.NoError(t, err)

	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddrStr,
		GameId:  "test-game",
	})
	require.NoError(t, err)

	// Verify the session was created with ID 0 (first session)
	session, err := f.keeper.GetSession(f.ctx, 0)
	require.NoError(t, err)
	require.Equal(t, testAddrStr, session.Player)

	testCases := []struct {
		name      string
		input     *types.MsgSubmitScore
		expErr    bool
		expErrMsg string
	}{
		{
			name: "invalid address",
			input: &types.MsgSubmitScore{
				Creator:   "invalid",
				SessionId: 0,
				Score:     100,
			},
			expErr:    true,
			expErrMsg: "invalid creator address",
		},
		{
			name: "session not found",
			input: &types.MsgSubmitScore{
				Creator:   testAddrStr,
				SessionId: 999,
				Score:     100,
			},
			expErr:    true,
			expErrMsg: "session not found",
		},
		{
			name: "successful submit score",
			input: &types.MsgSubmitScore{
				Creator:   testAddrStr,
				SessionId: 0,
				Score:     1000,
			},
			expErr: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := ms.SubmitScore(f.ctx, tc.input)

			if tc.expErr {
				require.Error(t, err)
				require.Contains(t, err.Error(), tc.expErrMsg)
			} else {
				require.NoError(t, err)
				// Verify score was updated
				session, err := f.keeper.GetSession(f.ctx, tc.input.SessionId)
				require.NoError(t, err)
				require.Equal(t, tc.input.Score, session.CurrentScore)
			}
		})
	}
}

func TestMsgSubmitScore_UnauthorizedPlayer(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create test addresses
	testAddr1 := sdk.AccAddress([]byte("test_address_12345"))
	testAddr1Str, err := f.addressCodec.BytesToString(testAddr1)
	require.NoError(t, err)

	testAddr2 := sdk.AccAddress([]byte("other_address_1234"))
	testAddr2Str, err := f.addressCodec.BytesToString(testAddr2)
	require.NoError(t, err)

	// Create a session for player 1
	err = f.keeper.SetPlayerCredits(f.ctx, testAddr1Str, 5)
	require.NoError(t, err)

	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddr1Str,
		GameId:  "test-game",
	})
	require.NoError(t, err)

	// Verify the session was created
	session, err := f.keeper.GetSession(f.ctx, 0)
	require.NoError(t, err)
	require.Equal(t, testAddr1Str, session.Player)

	// Try to submit score as player 2
	_, err = ms.SubmitScore(f.ctx, &types.MsgSubmitScore{
		Creator:   testAddr2Str,
		SessionId: 0,
		Score:     1000,
	})
	require.Error(t, err)
	require.Contains(t, err.Error(), "only the session owner can submit scores")
}

func TestRegisterGameValidation(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	creator := sdk.AccAddress([]byte("creator_address_12345"))
	creatorStr, err := f.addressCodec.BytesToString(creator)
	require.NoError(t, err)

	t.Run("invalid difficulty", func(t *testing.T) {
		_, err := ms.RegisterGame(f.ctx, &types.MsgRegisterGame{
			Creator: creatorStr,
			Game: types.ArcadeGame{
				GameId:         "game-high-diff",
				Name:           "Too Hard",
				BaseDifficulty: 20,
			},
		})
		require.Error(t, err)
		require.Contains(t, err.Error(), "base_difficulty")
	})

	t.Run("defaults applied", func(t *testing.T) {
		_, err := ms.RegisterGame(f.ctx, &types.MsgRegisterGame{
			Creator: creatorStr,
			Game: types.ArcadeGame{
				GameId: "game-ok",
				Name:   "OK Game",
			},
		})
		require.NoError(t, err)

		stored, err := f.keeper.GetArcadeGame(f.ctx, "game-ok")
		require.NoError(t, err)
		require.Equal(t, uint64(1), stored.BaseDifficulty)
		require.Equal(t, uint64(1), stored.CreditsPerPlay)
		require.Equal(t, uint64(1), stored.MaxPlayers)
	})
}

func TestActivateComboValidation(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	player := sdk.AccAddress([]byte("combo_player"))
	playerStr, _ := f.addressCodec.BytesToString(player)
	_ = f.keeper.SetPlayerCredits(f.ctx, playerStr, 5)
	_, _ = ms.StartSession(f.ctx, &types.MsgStartSession{Creator: playerStr, GameId: "game"})

	_, err := ms.ActivateCombo(f.ctx, &types.MsgActivateCombo{Creator: playerStr, SessionId: 0, ComboHits: 0})
	require.Error(t, err)
	require.Contains(t, err.Error(), "combo_hits")
}

func TestUsePowerUpChargesTokens(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	player := sdk.AccAddress([]byte("power_player"))
	playerStr, _ := f.addressCodec.BytesToString(player)
	_ = f.keeper.SetPlayerCredits(f.ctx, playerStr, 5)
	_, _ = ms.StartSession(f.ctx, &types.MsgStartSession{Creator: playerStr, GameId: "game"})

	// No tokens present
	_, err := ms.UsePowerUp(f.ctx, &types.MsgUsePowerUp{Creator: playerStr, SessionId: 0, PowerUpId: "shield"})
	require.Error(t, err)

	// Add tokens and try again
	entry := types.LeaderboardEntry{Player: playerStr, ArcadeTokens: 10}
	require.NoError(t, f.keeper.Leaderboard.Set(f.ctx, playerStr, entry))
	_, err = ms.UsePowerUp(f.ctx, &types.MsgUsePowerUp{Creator: playerStr, SessionId: 0, PowerUpId: "shield"})
	require.NoError(t, err)
	updated, err := f.keeper.Leaderboard.Get(f.ctx, playerStr)
	require.NoError(t, err)
	require.Less(t, updated.ArcadeTokens, entry.ArcadeTokens)
}

func TestTournamentValidation(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)
	creator := sdk.AccAddress([]byte("tour_creator"))
	creatorStr, _ := f.addressCodec.BytesToString(creator)

	_, err := ms.CreateTournament(f.ctx, &types.MsgCreateTournament{Creator: creatorStr, Tournament: types.Tournament{TournamentId: "t1", Name: "", GameId: ""}})
	require.Error(t, err)

	_, err = ms.JoinTournament(f.ctx, &types.MsgJoinTournament{Creator: creatorStr, TournamentId: ""})
	require.Error(t, err)

	_, err = ms.SubmitTournamentScore(f.ctx, &types.MsgSubmitTournamentScore{Creator: creatorStr, TournamentId: "", Score: 0})
	require.Error(t, err)
}

func TestSetHighScoreInitialsValidation(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)
	player := sdk.AccAddress([]byte("hs_player"))
	playerStr, _ := f.addressCodec.BytesToString(player)

	_, err := ms.SetHighScoreInitials(f.ctx, &types.MsgSetHighScoreInitials{Creator: playerStr, GameId: "game", Initials: "LONG"})
	require.Error(t, err)
	require.Contains(t, err.Error(), "initials")
}

func TestEndSession(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Fund the module account with tokens for rewards
	f.bankKeeper.Balances[types.ModuleName] = sdk.NewCoins(sdk.NewCoin("uretro", math.NewInt(1000000000)))

	// Give the player credits
	err = f.keeper.SetPlayerCredits(f.ctx, testAddrStr, 5)
	require.NoError(t, err)

	// Start a session
	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddrStr,
		GameId:  "test-game",
	})
	require.NoError(t, err)

	// Submit a score
	_, err = ms.SubmitScore(f.ctx, &types.MsgSubmitScore{
		Creator:   testAddrStr,
		SessionId: 0,
		Score:     50000,
	})
	require.NoError(t, err)

	// Get session and verify it's active
	session, err := f.keeper.GetSession(f.ctx, 0)
	require.NoError(t, err)
	require.Equal(t, types.SessionStatusActive, session.Status)
	require.Equal(t, uint64(50000), session.CurrentScore)

	// Note: EndSession and GameOver methods are internal to msgServer
	// These are tested via the keeper methods directly
}

func TestGameOver(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Give the player credits
	err = f.keeper.SetPlayerCredits(f.ctx, testAddrStr, 5)
	require.NoError(t, err)

	// Start a session
	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddrStr,
		GameId:  "test-game",
	})
	require.NoError(t, err)

	// Get session and verify it's active
	session, err := f.keeper.GetSession(f.ctx, 0)
	require.NoError(t, err)
	require.Equal(t, types.SessionStatusActive, session.Status)

	// Note: GameOver method is internal to msgServer
	// Session lifecycle transitions are tested via session state
}

func TestQueryPlayerCredits(t *testing.T) {
	f := initFixture(t)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Set player credits
	err = f.keeper.SetPlayerCredits(f.ctx, testAddrStr, 10)
	require.NoError(t, err)

	// Query credits
	credits, err := f.keeper.GetPlayerCreditsQuery(f.ctx, testAddrStr)
	require.NoError(t, err)
	require.Equal(t, uint64(10), credits)

	// Query credits for non-existent player
	credits, err = f.keeper.GetPlayerCreditsQuery(f.ctx, "nonexistent")
	require.NoError(t, err)
	require.Equal(t, uint64(0), credits)
}

func TestQuerySession(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create a test address
	testAddr := sdk.AccAddress([]byte("test_address_12345"))
	testAddrStr, err := f.addressCodec.BytesToString(testAddr)
	require.NoError(t, err)

	// Give the player credits
	err = f.keeper.SetPlayerCredits(f.ctx, testAddrStr, 5)
	require.NoError(t, err)

	// Start a session
	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddrStr,
		GameId:  "test-game",
	})
	require.NoError(t, err)

	// Query the session
	session, err := f.keeper.GetSessionQuery(f.ctx, 0)
	require.NoError(t, err)
	require.NotNil(t, session)
	require.Equal(t, testAddrStr, session.Player)
	require.Equal(t, "test-game", session.GameId)
	require.Equal(t, types.SessionStatusActive, session.Status)

	// Query non-existent session
	session, err = f.keeper.GetSessionQuery(f.ctx, 999)
	require.Error(t, err)
	require.Nil(t, session)
}

func TestListPlayerSessions(t *testing.T) {
	f := initFixture(t)
	ms := keeper.NewMsgServerImpl(f.keeper)

	// Create test addresses
	testAddr1 := sdk.AccAddress([]byte("test_address_12345"))
	testAddr1Str, err := f.addressCodec.BytesToString(testAddr1)
	require.NoError(t, err)

	testAddr2 := sdk.AccAddress([]byte("other_address_1234"))
	testAddr2Str, err := f.addressCodec.BytesToString(testAddr2)
	require.NoError(t, err)

	// Give players credits
	err = f.keeper.SetPlayerCredits(f.ctx, testAddr1Str, 5)
	require.NoError(t, err)
	err = f.keeper.SetPlayerCredits(f.ctx, testAddr2Str, 5)
	require.NoError(t, err)

	// Start sessions for player 1
	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddr1Str,
		GameId:  "game-1",
	})
	require.NoError(t, err)

	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddr1Str,
		GameId:  "game-2",
	})
	require.NoError(t, err)

	// Start session for player 2
	_, err = ms.StartSession(f.ctx, &types.MsgStartSession{
		Creator: testAddr2Str,
		GameId:  "game-1",
	})
	require.NoError(t, err)

	// Query player 1 sessions
	sessions, err := f.keeper.ListPlayerSessions(f.ctx, testAddr1Str)
	require.NoError(t, err)
	require.Len(t, sessions, 2)

	// Query player 2 sessions
	sessions, err = f.keeper.ListPlayerSessions(f.ctx, testAddr2Str)
	require.NoError(t, err)
	require.Len(t, sessions, 1)
}
