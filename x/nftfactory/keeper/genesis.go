package keeper

import (
	"context"

	"cosmossdk.io/collections"

	"retrochain/x/nftfactory/types"
)

func (k Keeper) InitGenesis(ctx context.Context, gs types.GenesisState) error {
	if err := gs.Validate(); err != nil {
		return err
	}

	for _, ca := range gs.ClassAuthorities {
		if err := k.ClassAdmin.Set(ctx, ca.ClassId, ca.Admin); err != nil {
			return err
		}
	}

	for _, cc := range gs.CreatorClasses {
		pair := collections.Join(cc.Creator, cc.ClassId)
		if err := k.CreatorClasses.Set(ctx, pair, true); err != nil {
			return err
		}
	}

	return nil
}

func (k Keeper) ExportGenesis(ctx context.Context) (types.GenesisState, error) {
	gen := *types.DefaultGenesis()

	err := k.ClassAdmin.Walk(ctx, nil, func(classID, admin string) (bool, error) {
		gen.ClassAuthorities = append(gen.ClassAuthorities, types.ClassAuthority{ClassId: classID, Admin: admin})
		return false, nil
	})
	if err != nil {
		return types.GenesisState{}, err
	}

	err = k.CreatorClasses.Walk(ctx, nil, func(key collections.Pair[string, string], _ bool) (bool, error) {
		gen.CreatorClasses = append(gen.CreatorClasses, types.CreatorClass{Creator: key.K1(), ClassId: key.K2()})
		return false, nil
	})
	if err != nil {
		return types.GenesisState{}, err
	}

	return gen, nil
}
