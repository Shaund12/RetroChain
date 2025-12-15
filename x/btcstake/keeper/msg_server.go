package keeper

import (
	"context"

	math "cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"

	"retrochain/x/btcstake/types"
)

type msgServer struct {
	Keeper
}

var _ types.MsgServer = msgServer{}

func NewMsgServerImpl(k Keeper) types.MsgServer {
	return &msgServer{Keeper: k}
}

func (m msgServer) UpdateParams(ctx context.Context, req *types.MsgUpdateParams) (*types.MsgUpdateParamsResponse, error) {
	if req == nil {
		return nil, types.ErrInvalidSigner
	}
	if err := req.Params.Validate(); err != nil {
		return nil, err
	}
	if req.Authority == "" {
		return nil, types.ErrInvalidSigner
	}
	// authority-gated (by signer annotation)
	return &types.MsgUpdateParamsResponse{}, m.SetParams(ctx, req.Params)
}

func (m msgServer) Stake(ctx context.Context, req *types.MsgStake) (*types.MsgStakeResponse, error) {
	if req == nil {
		return nil, types.ErrInvalidAmount
	}
	amt, err := parseAmount(req.Amount)
	if err != nil {
		return nil, err
	}
	addr, err := sdk.AccAddressFromBech32(req.Creator)
	if err != nil {
		return nil, err
	}
	staked, err := m.StakeFor(ctx, addr, amt)
	if err != nil {
		return nil, err
	}
	return &types.MsgStakeResponse{StakedAmount: staked.String()}, nil
}

func (m msgServer) Unstake(ctx context.Context, req *types.MsgUnstake) (*types.MsgUnstakeResponse, error) {
	if req == nil {
		return nil, types.ErrInvalidAmount
	}
	amt, err := parseAmount(req.Amount)
	if err != nil {
		return nil, err
	}
	addr, err := sdk.AccAddressFromBech32(req.Creator)
	if err != nil {
		return nil, err
	}
	remaining, err := m.UnstakeFor(ctx, addr, amt)
	if err != nil {
		return nil, err
	}
	return &types.MsgUnstakeResponse{RemainingStake: remaining.String()}, nil
}

func (m msgServer) ClaimRewards(ctx context.Context, req *types.MsgClaimRewards) (*types.MsgClaimRewardsResponse, error) {
	if req == nil {
		return nil, types.ErrInvalidAmount
	}
	addr, err := sdk.AccAddressFromBech32(req.Creator)
	if err != nil {
		return nil, err
	}
	claimed, err := m.Keeper.ClaimRewards(ctx, addr)
	if err != nil {
		return nil, err
	}
	return &types.MsgClaimRewardsResponse{ClaimedUretro: claimed.String()}, nil
}

func (m msgServer) FundRewards(ctx context.Context, req *types.MsgFundRewards) (*types.MsgFundRewardsResponse, error) {
	if req == nil {
		return nil, types.ErrInvalidAmount
	}
	amt, ok := math.NewIntFromString(req.Amount)
	if !ok || !amt.IsPositive() {
		return nil, types.ErrInvalidAmount
	}
	addr, err := sdk.AccAddressFromBech32(req.Funder)
	if err != nil {
		return nil, err
	}
	if err := m.Keeper.FundRewards(ctx, addr, amt); err != nil {
		return nil, err
	}
	return &types.MsgFundRewardsResponse{}, nil
}
