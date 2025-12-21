package keeper

import (
	"context"

	"cosmossdk.io/collections"

	"retrochain/x/tokenfactory/types"
)

func (k Keeper) InitGenesis(ctx context.Context, gs types.GenesisState) error {
	if err := gs.Validate(); err != nil {
		return err
	}

	for _, da := range gs.DenomAuthorities {
		if err := k.DenomAdmin.Set(ctx, da.Denom, da.Admin); err != nil {
			return err
		}
	}

	for _, cd := range gs.CreatorDenoms {
		pair := collections.Join(cd.Creator, cd.Denom)
		if err := k.CreatorDenoms.Set(ctx, pair, true); err != nil {
			return err
		}
	}

	return nil
}

func (k Keeper) ExportGenesis(ctx context.Context) (types.GenesisState, error) {
	gen := *types.DefaultGenesis()

	err := k.DenomAdmin.Walk(ctx, nil, func(denom string, admin string) (bool, error) {
		gen.DenomAuthorities = append(gen.DenomAuthorities, types.DenomAuthority{Denom: denom, Admin: admin})
		return false, nil
	})
	if err != nil {
		return types.GenesisState{}, err
	}

	err = k.CreatorDenoms.Walk(ctx, nil, func(key collections.Pair[string, string], _ bool) (bool, error) {
		gen.CreatorDenoms = append(gen.CreatorDenoms, types.CreatorDenom{Creator: key.K1(), Denom: key.K2()})
		return false, nil
	})
	if err != nil {
		return types.GenesisState{}, err
	}

	return gen, nil
}
