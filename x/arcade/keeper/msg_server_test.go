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
