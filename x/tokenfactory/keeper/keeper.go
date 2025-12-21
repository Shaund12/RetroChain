package keeper

import (
	"context"
	"errors"
	"fmt"

	"cosmossdk.io/collections"
	"cosmossdk.io/core/address"
	"cosmossdk.io/core/store"
	"github.com/cosmos/cosmos-sdk/codec"

	"retrochain/x/tokenfactory/types"
)

type Keeper struct {
	storeService store.KVStoreService
	cdc          codec.Codec
	addressCodec address.Codec
	authority    []byte

	bankKeeper types.BankKeeper

	DenomAdmin    collections.Map[string, string]
	CreatorDenoms collections.Map[collections.Pair[string, string], bool]
}

func NewKeeper(
	storeService store.KVStoreService,
	custodyCodec codec.Codec,
	addressCodec address.Codec,
	authority []byte,
	bankKeeper types.BankKeeper,
) Keeper {
	if _, err := addressCodec.BytesToString(authority); err != nil {
		panic(fmt.Sprintf("invalid authority address %x: %s", authority, err))
	}

	sb := collections.NewSchemaBuilder(storeService)
	k := Keeper{
		storeService: storeService,
		cdc:          custodyCodec,
		addressCodec: addressCodec,
		authority:    authority,
		bankKeeper:   bankKeeper,
		DenomAdmin:   collections.NewMap(sb, types.DenomAdminKeyPrefix, "denom_admin", collections.StringKey, collections.StringValue),
		CreatorDenoms: collections.NewMap(
			sb,
			types.CreatorDenomsKeyPrefix,
			"creator_denoms",
			collections.PairKeyCodec(collections.StringKey, collections.StringKey),
			collections.BoolValue,
		),
	}
	if _, err := sb.Build(); err != nil {
		panic(err)
	}
	return k
}

func (k Keeper) GetAuthority() []byte { return k.authority }

func (k Keeper) GetAdmin(ctx context.Context, denom string) (string, error) {
	admin, err := k.DenomAdmin.Get(ctx, denom)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return "", types.ErrUnknownDenom
		}
		return "", err
	}
	return admin, nil
}

func (k Keeper) HasDenom(ctx context.Context, denom string) (bool, error) {
	_, err := k.DenomAdmin.Get(ctx, denom)
	if err == nil {
		return true, nil
	}
	if errors.Is(err, collections.ErrNotFound) {
		return false, nil
	}
	return false, err
}
