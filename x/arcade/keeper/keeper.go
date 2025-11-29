package keeper

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"cosmossdk.io/collections"
	"cosmossdk.io/core/address"
	corestore "cosmossdk.io/core/store"
	"github.com/cosmos/cosmos-sdk/codec"

	"retrochain/x/arcade/types"
)

// Keeper defines the arcade module keeper.
type Keeper struct {
	storeService corestore.KVStoreService
	cdc          codec.Codec
	addressCodec address.Codec
	// Address capable of executing a MsgUpdateParams message.
	// Typically, this should be the x/gov module account.
	authority []byte

	// Bank keeper for handling token transfers
	bankKeeper types.BankKeeper
	// Auth keeper for account management
	authKeeper types.AuthKeeper

	Schema         collections.Schema
	Params         collections.Item[types.Params]
	PlayerCredits  collections.Map[string, uint64]
	SessionCounter collections.Sequence
	// GameSessions stores game sessions as JSON bytes.
	// Note: We use JSON encoding because GameSession is not a protobuf message
	// and we're implementing this without modifying the proto files.
	// For production, consider defining GameSession in proto files and using
	// codec.CollValue for better type safety and performance.
	GameSessions collections.Map[uint64, []byte]
}

// NewKeeper creates a new arcade module Keeper instance
func NewKeeper(
	storeService corestore.KVStoreService,
	cdc codec.Codec,
	addressCodec address.Codec,
	authority []byte,
	bankKeeper types.BankKeeper,
	authKeeper types.AuthKeeper,
) Keeper {
	authorityStr, err := addressCodec.BytesToString(authority)
	if err != nil {
		panic(fmt.Sprintf("invalid authority address %x: %s", authority, err))
	}
	_ = authorityStr // validate conversion succeeded

	sb := collections.NewSchemaBuilder(storeService)

	k := Keeper{
		storeService: storeService,
		cdc:          cdc,
		addressCodec: addressCodec,
		authority:    authority,
		bankKeeper:   bankKeeper,
		authKeeper:   authKeeper,

		Params:         collections.NewItem(sb, types.ParamsKey, "params", codec.CollValue[types.Params](cdc)),
		PlayerCredits:  collections.NewMap(sb, types.PlayerCreditsKeyPrefix, "player_credits", collections.StringKey, collections.Uint64Value),
		SessionCounter: collections.NewSequence(sb, types.SessionCounterKey, "session_counter"),
		GameSessions:   collections.NewMap(sb, types.GameSessionKeyPrefix, "game_sessions", collections.Uint64Key, collections.BytesValue),
	}

	schema, err := sb.Build()
	if err != nil {
		panic(err)
	}
	k.Schema = schema

	return k
}

// GetAuthority returns the module's authority.
func (k Keeper) GetAuthority() []byte {
	return k.authority
}

// GetPlayerCredits returns the credits for a player.
func (k Keeper) GetPlayerCredits(ctx context.Context, player string) (uint64, error) {
	credits, err := k.PlayerCredits.Get(ctx, player)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return 0, nil
		}
		return 0, err
	}
	return credits, nil
}

// SetPlayerCredits sets the credits for a player.
func (k Keeper) SetPlayerCredits(ctx context.Context, player string, credits uint64) error {
	return k.PlayerCredits.Set(ctx, player, credits)
}

// GetSession returns a game session by ID.
// The session data is stored as JSON bytes and unmarshaled here.
func (k Keeper) GetSession(ctx context.Context, sessionID uint64) (types.GameSession, error) {
	data, err := k.GameSessions.Get(ctx, sessionID)
	if err != nil {
		return types.GameSession{}, err
	}
	var session types.GameSession
	if err := json.Unmarshal(data, &session); err != nil {
		return types.GameSession{}, err
	}
	return session, nil
}

// SetSession stores a game session.
// The session data is marshaled to JSON bytes for storage.
func (k Keeper) SetSession(ctx context.Context, session types.GameSession) error {
	data, err := json.Marshal(session)
	if err != nil {
		return err
	}
	return k.GameSessions.Set(ctx, session.SessionID, data)
}

// NextSessionID returns the next session ID and increments the counter.
func (k Keeper) NextSessionID(ctx context.Context) (uint64, error) {
	return k.SessionCounter.Next(ctx)
}
