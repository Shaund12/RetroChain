package keeper

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"cosmossdk.io/collections"
	collcodec "cosmossdk.io/collections/codec"
	"cosmossdk.io/core/address"
	"cosmossdk.io/core/store"
	math "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	sdk "github.com/cosmos/cosmos-sdk/types"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"

	"retrochain/x/btcstake/types"
)

type Keeper struct {
	storeService store.KVStoreService
	cdc          codec.Codec
	addressCodec address.Codec
	bankKeeper   types.BankKeeper

	// authority is the address that can update params.
	authority []byte

	Schema collections.Schema

	Params               collections.Item[types.Params]
	TotalStaked          collections.Item[math.Int]
	RewardIndex          collections.Item[math.LegacyDec]
	UndistributedRewards collections.Item[math.Int]
	Stake                collections.Map[string, math.Int]
	UserIndex            collections.Map[string, math.LegacyDec]
	PendingRewards       collections.Map[string, math.Int]
}

type intValueCodec struct{}

func (intValueCodec) Encode(value math.Int) ([]byte, error) { return []byte(value.String()), nil }
func (intValueCodec) Decode(bz []byte) (math.Int, error) {
	if len(bz) == 0 {
		return math.ZeroInt(), nil
	}
	v, ok := math.NewIntFromString(string(bz))
	if !ok {
		return math.Int{}, fmt.Errorf("invalid int: %q", string(bz))
	}
	return v, nil
}
func (c intValueCodec) EncodeJSON(value math.Int) ([]byte, error) { return c.Encode(value) }
func (c intValueCodec) DecodeJSON(bz []byte) (math.Int, error)    { return c.Decode(bz) }
func (intValueCodec) Stringify(value math.Int) string             { return value.String() }
func (intValueCodec) ValueType() string                           { return "btcstake/Int" }

type decValueCodec struct{}

func (decValueCodec) Encode(value math.LegacyDec) ([]byte, error) { return []byte(value.String()), nil }
func (decValueCodec) Decode(bz []byte) (math.LegacyDec, error) {
	if len(bz) == 0 {
		return math.LegacyZeroDec(), nil
	}
	v, err := math.LegacyNewDecFromStr(string(bz))
	if err != nil {
		return math.LegacyDec{}, err
	}
	return v, nil
}
func (c decValueCodec) EncodeJSON(value math.LegacyDec) ([]byte, error) { return c.Encode(value) }
func (c decValueCodec) DecodeJSON(bz []byte) (math.LegacyDec, error)    { return c.Decode(bz) }
func (decValueCodec) Stringify(value math.LegacyDec) string             { return value.String() }
func (decValueCodec) ValueType() string                                 { return "btcstake/LegacyDec" }

func NewKeeper(
	storeService store.KVStoreService,
	cdc codec.Codec,
	addressCodec address.Codec,
	authority []byte,
	bankKeeper types.BankKeeper,
) Keeper {
	authorityStr, err := addressCodec.BytesToString(authority)
	if err != nil {
		panic(fmt.Sprintf("invalid authority address %x: %s", authority, err))
	}
	_ = authorityStr

	sb := collections.NewSchemaBuilder(storeService)

	k := Keeper{
		storeService: storeService,
		cdc:          cdc,
		addressCodec: addressCodec,
		bankKeeper:   bankKeeper,
		authority:    authority,

		Params:               collections.NewItem(sb, types.ParamsKey, "params", codec.CollValue[types.Params](cdc)),
		TotalStaked:          collections.NewItem(sb, types.TotalStakedKey, "total_staked", intValueCodec{}),
		RewardIndex:          collections.NewItem(sb, types.RewardIndexKey, "reward_index", decValueCodec{}),
		UndistributedRewards: collections.NewItem(sb, types.UndistributedRewardsKey, "undistributed_rewards", intValueCodec{}),
		Stake:                collections.NewMap(sb, types.StakeKeyPrefix, "stake", collections.StringKey, intValueCodec{}),
		UserIndex:            collections.NewMap(sb, types.UserIndexKeyPrefix, "user_index", collections.StringKey, decValueCodec{}),
		PendingRewards:       collections.NewMap(sb, types.PendingRewardsKeyPrefix, "pending_rewards", collections.StringKey, intValueCodec{}),
	}

	schema, err := sb.Build()
	if err != nil {
		panic(err)
	}
	k.Schema = schema

	return k
}

func (k Keeper) Authority() []byte { return k.authority }

func (k Keeper) moduleAddress() sdk.AccAddress {
	return authtypes.NewModuleAddress(types.ModuleName)
}

func (k Keeper) receiptDenom() string { return "stwbtc" }

func (k Keeper) rewardDenom() string { return "uretro" }

func (k Keeper) GetParams(ctx context.Context) (types.Params, error) {
	p, err := k.Params.Get(ctx)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return types.DefaultParams(), nil
		}
		return types.Params{}, err
	}
	return p, nil
}

func (k Keeper) SetParams(ctx context.Context, p types.Params) error {
	if err := p.Validate(); err != nil {
		return err
	}
	return k.Params.Set(ctx, p)
}

func (k Keeper) InitGenesis(ctx context.Context, gs types.GenesisState) error {
	if err := gs.Params.Validate(); err != nil {
		return err
	}
	if err := k.SetParams(ctx, gs.Params); err != nil {
		return err
	}
	// Initialize indexes.
	if err := k.TotalStaked.Set(ctx, math.ZeroInt()); err != nil {
		return err
	}
	if err := k.RewardIndex.Set(ctx, math.LegacyZeroDec()); err != nil {
		return err
	}
	if err := k.UndistributedRewards.Set(ctx, math.ZeroInt()); err != nil {
		return err
	}
	return nil
}

func (k Keeper) ExportGenesis(ctx context.Context) (types.GenesisState, error) {
	p, err := k.GetParams(ctx)
	if err != nil {
		return types.GenesisState{}, err
	}
	return types.GenesisState{Params: p}, nil
}

func (k Keeper) getIntOrZero(ctx context.Context, item collections.Item[math.Int]) (math.Int, error) {
	v, err := item.Get(ctx)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return math.ZeroInt(), nil
		}
		return math.Int{}, err
	}
	return v, nil
}

func (k Keeper) getDecOrZero(ctx context.Context, item collections.Item[math.LegacyDec]) (math.LegacyDec, error) {
	v, err := item.Get(ctx)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return math.LegacyZeroDec(), nil
		}
		return math.LegacyDec{}, err
	}
	return v, nil
}

func (k Keeper) getStake(ctx context.Context, addr string) (math.Int, error) {
	v, err := k.Stake.Get(ctx, addr)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return math.ZeroInt(), nil
		}
		return math.Int{}, err
	}
	return v, nil
}

func (k Keeper) getUserIndex(ctx context.Context, addr string) (math.LegacyDec, error) {
	v, err := k.UserIndex.Get(ctx, addr)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return math.LegacyZeroDec(), nil
		}
		return math.LegacyDec{}, err
	}
	return v, nil
}

func (k Keeper) getPending(ctx context.Context, addr string) (math.Int, error) {
	v, err := k.PendingRewards.Get(ctx, addr)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return math.ZeroInt(), nil
		}
		return math.Int{}, err
	}
	return v, nil
}

func parseAmount(amountStr string) (math.Int, error) {
	amt, ok := math.NewIntFromString(amountStr)
	if !ok || !amt.IsPositive() {
		return math.Int{}, types.ErrInvalidAmount
	}
	return amt, nil
}

func (k Keeper) distributeRewards(ctx context.Context, amount math.Int) error {
	if !amount.IsPositive() {
		return nil
	}
	total, err := k.getIntOrZero(ctx, k.TotalStaked)
	if err != nil {
		return err
	}
	if !total.IsPositive() {
		und, err := k.getIntOrZero(ctx, k.UndistributedRewards)
		if err != nil {
			return err
		}
		return k.UndistributedRewards.Set(ctx, und.Add(amount))
	}

	idx, err := k.getDecOrZero(ctx, k.RewardIndex)
	if err != nil {
		return err
	}

	// rewardIndex += amount/total
	delta := math.LegacyNewDecFromInt(amount).QuoInt(total)
	return k.RewardIndex.Set(ctx, idx.Add(delta))
}

func (k Keeper) maybeDistributeUndistributed(ctx context.Context) error {
	und, err := k.getIntOrZero(ctx, k.UndistributedRewards)
	if err != nil {
		return err
	}
	if !und.IsPositive() {
		return nil
	}
	total, err := k.getIntOrZero(ctx, k.TotalStaked)
	if err != nil {
		return err
	}
	if !total.IsPositive() {
		return nil
	}
	// clear then distribute to avoid double-count if distributeRewards errors later.
	if err := k.UndistributedRewards.Set(ctx, math.ZeroInt()); err != nil {
		return err
	}
	return k.distributeRewards(ctx, und)
}

func (k Keeper) settle(ctx context.Context, addr string) (math.Int, error) {
	if err := k.maybeDistributeUndistributed(ctx); err != nil {
		return math.Int{}, err
	}

	stake, err := k.getStake(ctx, addr)
	if err != nil {
		return math.Int{}, err
	}
	pending, err := k.getPending(ctx, addr)
	if err != nil {
		return math.Int{}, err
	}
	userIdx, err := k.getUserIndex(ctx, addr)
	if err != nil {
		return math.Int{}, err
	}
	globalIdx, err := k.getDecOrZero(ctx, k.RewardIndex)
	if err != nil {
		return math.Int{}, err
	}

	if stake.IsPositive() {
		delta := globalIdx.Sub(userIdx)
		if delta.IsPositive() {
			accrued := delta.MulInt(stake).TruncateInt()
			if accrued.IsPositive() {
				pending = pending.Add(accrued)
			}
		}
	}

	if err := k.PendingRewards.Set(ctx, addr, pending); err != nil {
		return math.Int{}, err
	}
	if err := k.UserIndex.Set(ctx, addr, globalIdx); err != nil {
		return math.Int{}, err
	}
	return pending, nil
}

func (k Keeper) StakeFor(ctx context.Context, staker sdk.AccAddress, amount math.Int) (math.Int, error) {
	p, err := k.GetParams(ctx)
	if err != nil {
		return math.Int{}, err
	}
	if p.AllowedDenom == "" {
		return math.Int{}, types.ErrParamsNotSet
	}

	// Settle rewards before mutating stake.
	if _, err := k.settle(ctx, staker.String()); err != nil {
		return math.Int{}, err
	}

	// Deposit underlying into module account.
	deposit := sdk.NewCoins(sdk.NewCoin(p.AllowedDenom, amount))
	if err := k.bankKeeper.SendCoinsFromAccountToModule(ctx, staker, types.ModuleName, deposit); err != nil {
		return math.Int{}, err
	}

	// Mint receipt token to the user (1:1, same base units).
	receipt := sdk.NewCoins(sdk.NewCoin(k.receiptDenom(), amount))
	if err := k.bankKeeper.MintCoins(ctx, types.ModuleName, receipt); err != nil {
		return math.Int{}, err
	}
	if err := k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, staker, receipt); err != nil {
		return math.Int{}, err
	}

	// Track stake and total.
	currentStake, err := k.getStake(ctx, staker.String())
	if err != nil {
		return math.Int{}, err
	}
	if err := k.Stake.Set(ctx, staker.String(), currentStake.Add(amount)); err != nil {
		return math.Int{}, err
	}

	total, err := k.getIntOrZero(ctx, k.TotalStaked)
	if err != nil {
		return math.Int{}, err
	}
	if err := k.TotalStaked.Set(ctx, total.Add(amount)); err != nil {
		return math.Int{}, err
	}

	bal := k.bankKeeper.GetBalance(ctx, staker, k.receiptDenom())
	return bal.Amount, nil
}

func (k Keeper) UnstakeFor(ctx context.Context, staker sdk.AccAddress, amount math.Int) (math.Int, error) {
	p, err := k.GetParams(ctx)
	if err != nil {
		return math.Int{}, err
	}
	if p.AllowedDenom == "" {
		return math.Int{}, types.ErrParamsNotSet
	}

	// Settle rewards before mutating stake.
	if _, err := k.settle(ctx, staker.String()); err != nil {
		return math.Int{}, err
	}

	// Require the caller to hold enough receipt tokens.
	currentStake, err := k.getStake(ctx, staker.String())
	if err != nil {
		return math.Int{}, err
	}
	if currentStake.LT(amount) {
		return math.Int{}, types.ErrInsufficientStake
	}

	// Require the caller to hold enough receipt tokens.
	receiptBal := k.bankKeeper.GetBalance(ctx, staker, k.receiptDenom())
	if receiptBal.Amount.LT(amount) {
		return math.Int{}, types.ErrInsufficientStake
	}

	// Pull receipt tokens into module account, then burn them.
	receipt := sdk.NewCoins(sdk.NewCoin(k.receiptDenom(), amount))
	if err := k.bankKeeper.SendCoinsFromAccountToModule(ctx, staker, types.ModuleName, receipt); err != nil {
		return math.Int{}, err
	}
	if err := k.bankKeeper.BurnCoins(ctx, types.ModuleName, receipt); err != nil {
		return math.Int{}, err
	}

	// Release underlying back to the user.
	underlying := sdk.NewCoins(sdk.NewCoin(p.AllowedDenom, amount))
	if err := k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, staker, underlying); err != nil {
		return math.Int{}, err
	}

	total, err := k.getIntOrZero(ctx, k.TotalStaked)
	if err != nil {
		return math.Int{}, err
	}
	if err := k.TotalStaked.Set(ctx, total.Sub(amount)); err != nil {
		return math.Int{}, err
	}

	// Persist reduced stake amount.
	newStake := currentStake.Sub(amount)
	if err := k.Stake.Set(ctx, staker.String(), newStake); err != nil {
		return math.Int{}, err
	}

	remaining := k.bankKeeper.GetBalance(ctx, staker, k.receiptDenom())
	return remaining.Amount, nil
}

func (k Keeper) FundRewards(ctx context.Context, funder sdk.AccAddress, amount math.Int) error {
	if !amount.IsPositive() {
		return types.ErrInvalidAmount
	}

	rewardCoins := sdk.NewCoins(sdk.NewCoin(k.rewardDenom(), amount))
	if err := k.bankKeeper.SendCoinsFromAccountToModule(ctx, funder, types.ModuleName, rewardCoins); err != nil {
		return err
	}

	// Distribute or park as undistributed if no stake.
	if err := k.distributeRewards(ctx, amount); err != nil {
		return err
	}
	return nil
}

func (k Keeper) ClaimRewards(ctx context.Context, claimer sdk.AccAddress) (math.Int, error) {
	pending, err := k.settle(ctx, claimer.String())
	if err != nil {
		return math.Int{}, err
	}
	if !pending.IsPositive() {
		return math.ZeroInt(), nil
	}

	// Pay out pending rewards in reward denom.
	coins := sdk.NewCoins(sdk.NewCoin(k.rewardDenom(), pending))
	if err := k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, claimer, coins); err != nil {
		return math.Int{}, err
	}

	// Clear pending.
	if err := k.PendingRewards.Set(ctx, claimer.String(), math.ZeroInt()); err != nil {
		return math.Int{}, err
	}
	return pending, nil
}

func (k Keeper) GetPoolInfo(ctx context.Context) (allowedDenom string, totalStaked math.Int, rewardBal math.Int, undistributed math.Int, rewardIndex math.LegacyDec, err error) {
	p, err := k.GetParams(ctx)
	if err != nil {
		return "", math.Int{}, math.Int{}, math.Int{}, math.LegacyDec{}, err
	}
	allowedDenom = p.AllowedDenom
	if strings.TrimSpace(allowedDenom) == "" {
		return allowedDenom, math.ZeroInt(), math.ZeroInt(), math.ZeroInt(), math.LegacyZeroDec(), nil
	}
	balCoin := k.bankKeeper.GetBalance(ctx, k.moduleAddress(), allowedDenom)
	totalStaked = balCoin.Amount
	rewardBal = k.bankKeeper.GetBalance(ctx, k.moduleAddress(), k.rewardDenom()).Amount
	undistributed, _ = k.getIntOrZero(ctx, k.UndistributedRewards)
	rewardIndex, _ = k.getDecOrZero(ctx, k.RewardIndex)
	return allowedDenom, totalStaked, rewardBal, undistributed, rewardIndex, nil
}

var _ collcodec.ValueCodec[math.Int] = intValueCodec{}
var _ collcodec.ValueCodec[math.LegacyDec] = decValueCodec{}
