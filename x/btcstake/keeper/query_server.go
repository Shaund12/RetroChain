package keeper

import (
	"context"

	sdk "github.com/cosmos/cosmos-sdk/types"

	"retrochain/x/btcstake/types"
)

type queryServer struct {
	Keeper
}

var _ types.QueryServer = queryServer{}

func NewQueryServerImpl(k Keeper) types.QueryServer {
	return &queryServer{Keeper: k}
}

func (q queryServer) Params(ctx context.Context, _ *types.QueryParamsRequest) (*types.QueryParamsResponse, error) {
	p, err := q.GetParams(ctx)
	if err != nil {
		return nil, err
	}
	return &types.QueryParamsResponse{Params: p}, nil
}

func (q queryServer) Stake(ctx context.Context, req *types.QueryStakeRequest) (*types.QueryStakeResponse, error) {
	if req == nil {
		return nil, types.ErrInvalidAmount
	}
	addr, err := sdk.AccAddressFromBech32(req.Address)
	if err != nil {
		return nil, err
	}
	bal := q.bankKeeper.GetBalance(ctx, addr, q.receiptDenom())
	return &types.QueryStakeResponse{StakedAmount: bal.Amount.String()}, nil
}

func (q queryServer) PendingRewards(ctx context.Context, req *types.QueryPendingRewardsRequest) (*types.QueryPendingRewardsResponse, error) {
	if req == nil {
		return nil, types.ErrInvalidAmount
	}
	addr, err := sdk.AccAddressFromBech32(req.Address)
	if err != nil {
		return nil, err
	}
	pending, err := q.settle(ctx, addr.String())
	if err != nil {
		return nil, err
	}
	return &types.QueryPendingRewardsResponse{PendingUretro: pending.String()}, nil
}

func (q queryServer) Pool(ctx context.Context, _ *types.QueryPoolRequest) (*types.QueryPoolResponse, error) {
	// Ensure any parked rewards are distributed if stake exists.
	_ = q.maybeDistributeUndistributed(ctx)

	allowedDenom, totalStaked, rewardBal, und, idx, err := q.GetPoolInfo(ctx)
	if err != nil {
		return nil, err
	}
	return &types.QueryPoolResponse{
		AllowedDenom:        allowedDenom,
		TotalStakedAmount:   totalStaked.String(),
		RewardBalanceUretro: rewardBal.String(),
		UndistributedUretro: und.String(),
		RewardIndex:         idx.String(),
	}, nil
}
