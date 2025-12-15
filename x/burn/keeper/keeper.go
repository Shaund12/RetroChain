package keeper

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"cosmossdk.io/collections"
	collcodec "cosmossdk.io/collections/codec"
	"cosmossdk.io/core/store"
	math "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	sdk "github.com/cosmos/cosmos-sdk/types"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	bankkeeper "github.com/cosmos/cosmos-sdk/x/bank/keeper"
	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"

	"retrochain/x/burn/types"
)

// Keeper manages burn params and logic.
type Keeper struct {
	storeService store.KVStoreService
	bankKeeper   bankkeeper.Keeper
	cdc          codec.Codec

	Params collections.Item[types.Params]
}

var _ collcodec.ValueCodec[types.Params] = paramsValueCodec{}

type paramsValueCodec struct{}

func (paramsValueCodec) Encode(value types.Params) ([]byte, error) { return json.Marshal(value) }
func (paramsValueCodec) Decode(bz []byte) (types.Params, error) {
	var p types.Params
	return p, json.Unmarshal(bz, &p)
}
func (c paramsValueCodec) EncodeJSON(value types.Params) ([]byte, error) { return c.Encode(value) }
func (c paramsValueCodec) DecodeJSON(bz []byte) (types.Params, error)    { return c.Decode(bz) }
func (paramsValueCodec) Stringify(value types.Params) string {
	return fmt.Sprintf("fee=%s,prov=%s", value.FeeBurnRate.String(), value.ProvisionBurnRate.String())
}
func (paramsValueCodec) ValueType() string { return "burn/Params" }

func NewKeeper(storeService store.KVStoreService, cdc codec.Codec, bankKeeper bankkeeper.Keeper) Keeper {
	sb := collections.NewSchemaBuilder(storeService)
	k := Keeper{storeService: storeService, bankKeeper: bankKeeper, cdc: cdc,
		Params: collections.NewItem(sb, types.ParamsKey, "burn_params", paramsValueCodec{}),
	}
	if _, err := sb.Build(); err != nil {
		panic(err)
	}
	return k
}

// GetParams returns current params or default if unset.
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

// SetParams stores module params.
func (k Keeper) SetParams(ctx context.Context, p types.Params) error {
	if err := p.Validate(); err != nil {
		return err
	}
	return k.Params.Set(ctx, p)
}

// InitGenesis sets params.
func (k Keeper) InitGenesis(ctx context.Context, p types.Params) error { return k.SetParams(ctx, p) }

// ExportGenesis returns params.
func (k Keeper) ExportGenesis(ctx context.Context) (types.Params, error) { return k.GetParams(ctx) }

// BeginBlock burns fee collector balance fractions.
func (k Keeper) BeginBlock(ctx sdk.Context) {
	params, err := k.GetParams(ctx)
	if err != nil {
		return
	}
	feeCollectorAddr := authtypes.NewModuleAddress(authtypes.FeeCollectorName)
	balance := k.bankKeeper.GetAllBalances(ctx, feeCollectorAddr)
	if balance.IsZero() {
		return
	}

	burnCoins := sdk.NewCoins()

	// Provision burn applied first
	if params.ProvisionBurnRate.IsPositive() {
		portion := mulDec(balance, params.ProvisionBurnRate)
		burnCoins = burnCoins.Add(portion...)
		balance = balance.Sub(portion...)
	}

	// Fee burn applied on remaining balance
	if params.FeeBurnRate.IsPositive() && !balance.IsZero() {
		portion := mulDec(balance, params.FeeBurnRate)
		burnCoins = burnCoins.Add(portion...)
	}

	if burnCoins.IsZero() {
		return
	}
	// bankKeeper requires module name for BurnCoins
	_ = k.bankKeeper.BurnCoins(ctx, authtypes.FeeCollectorName, burnCoins)
}

// mulDec applies a decimal rate to all coins (floor per denom).
func mulDec(coins sdk.Coins, rate math.LegacyDec) sdk.Coins {
	if rate.IsZero() {
		return sdk.NewCoins()
	}
	out := sdk.NewCoins()
	for _, c := range coins {
		amt := rate.MulInt(c.Amount).TruncateInt()
		if amt.IsPositive() {
			out = out.Add(sdk.NewCoin(c.Denom, amt))
		}
	}
	return out
}

// ParamsSubspace returns the param key table for module registration.
func (k Keeper) ParamsSubspace() *paramstypes.KeyTable {
	kt := types.ParamKeyTable()
	return &kt
}
