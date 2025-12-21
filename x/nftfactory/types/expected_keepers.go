package types

import (
	"context"

	"cosmossdk.io/x/nft"

	sdk "github.com/cosmos/cosmos-sdk/types"
)

type NFTKeeper interface {
	HasClass(ctx context.Context, classID string) bool
	SaveClass(ctx context.Context, class nft.Class) error
	Mint(ctx context.Context, token nft.NFT, receiver sdk.AccAddress) error
}
