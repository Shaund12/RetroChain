package keeper

import (
	"context"
	"errors"
	"fmt"

	"cosmossdk.io/collections"
	"cosmossdk.io/core/address"
	"cosmossdk.io/core/store"
	"github.com/cosmos/cosmos-sdk/codec"

	"retrochain/x/nftfactory/types"
)

type Keeper struct {
	storeService store.KVStoreService
	cdc          codec.Codec
	addressCodec address.Codec
	authority    []byte

	nftKeeper types.NFTKeeper

	ClassAdmin     collections.Map[string, string]
	CreatorClasses collections.Map[collections.Pair[string, string], bool]
}

func NewKeeper(
	storeService store.KVStoreService,
	cdc codec.Codec,
	addressCodec address.Codec,
	authority []byte,
	nftKeeper types.NFTKeeper,
) Keeper {
	if _, err := addressCodec.BytesToString(authority); err != nil {
		panic(fmt.Sprintf("invalid authority address %x: %s", authority, err))
	}

	sb := collections.NewSchemaBuilder(storeService)
	k := Keeper{
		storeService:   storeService,
		cdc:            cdc,
		addressCodec:   addressCodec,
		authority:      authority,
		nftKeeper:      nftKeeper,
		ClassAdmin:     collections.NewMap(sb, types.ClassAdminKeyPrefix, "class_admin", collections.StringKey, collections.StringValue),
		CreatorClasses: collections.NewMap(sb, types.CreatorClassesKeyPrefix, "creator_classes", collections.PairKeyCodec(collections.StringKey, collections.StringKey), collections.BoolValue),
	}
	if _, err := sb.Build(); err != nil {
		panic(err)
	}
	return k
}

func (k Keeper) GetAuthority() []byte { return k.authority }

func (k Keeper) GetAdmin(ctx context.Context, classID string) (string, error) {
	admin, err := k.ClassAdmin.Get(ctx, classID)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return "", types.ErrUnknownClass
		}
		return "", err
	}
	return admin, nil
}
