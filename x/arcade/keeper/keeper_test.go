package keeper_test

import (
	"context"
	"testing"

	"cosmossdk.io/core/address"
	storetypes "cosmossdk.io/store/types"
	addresscodec "github.com/cosmos/cosmos-sdk/codec/address"
	"github.com/cosmos/cosmos-sdk/runtime"
	"github.com/cosmos/cosmos-sdk/testutil"
	sdk "github.com/cosmos/cosmos-sdk/types"
	moduletestutil "github.com/cosmos/cosmos-sdk/types/module/testutil"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"

	"retrochain/x/arcade/keeper"
	module "retrochain/x/arcade/module"
	"retrochain/x/arcade/types"
)

// MockBankKeeper is a mock implementation of the BankKeeper interface
type MockBankKeeper struct {
	Balances map[string]sdk.Coins
}

func NewMockBankKeeper() *MockBankKeeper {
	return &MockBankKeeper{
		Balances: make(map[string]sdk.Coins),
	}
}

func (m *MockBankKeeper) SpendableCoins(_ context.Context, addr sdk.AccAddress) sdk.Coins {
	return m.Balances[addr.String()]
}

func (m *MockBankKeeper) SendCoinsFromAccountToModule(_ context.Context, senderAddr sdk.AccAddress, recipientModule string, amt sdk.Coins) error {
	balance := m.Balances[senderAddr.String()]
	if !balance.IsAllGTE(amt) {
		return types.ErrInsufficientFund
	}
	m.Balances[senderAddr.String()] = balance.Sub(amt...)
	moduleBalance := m.Balances[recipientModule]
	m.Balances[recipientModule] = moduleBalance.Add(amt...)
	return nil
}

func (m *MockBankKeeper) SendCoinsFromModuleToAccount(_ context.Context, senderModule string, recipientAddr sdk.AccAddress, amt sdk.Coins) error {
	balance := m.Balances[senderModule]
	if !balance.IsAllGTE(amt) {
		return types.ErrInsufficientFund
	}
	m.Balances[senderModule] = balance.Sub(amt...)
	userBalance := m.Balances[recipientAddr.String()]
	m.Balances[recipientAddr.String()] = userBalance.Add(amt...)
	return nil
}

type fixture struct {
	ctx          context.Context
	keeper       keeper.Keeper
	addressCodec address.Codec
	bankKeeper   *MockBankKeeper
}

func initFixture(t *testing.T) *fixture {
	t.Helper()

	encCfg := moduletestutil.MakeTestEncodingConfig(module.AppModule{})
	addressCodec := addresscodec.NewBech32Codec(sdk.GetConfig().GetBech32AccountAddrPrefix())
	storeKey := storetypes.NewKVStoreKey(types.StoreKey)

	storeService := runtime.NewKVStoreService(storeKey)
	ctx := testutil.DefaultContextWithDB(t, storeKey, storetypes.NewTransientStoreKey("transient_test")).Ctx

	authority := authtypes.NewModuleAddress(types.GovModuleName)
	bankKeeper := NewMockBankKeeper()

	k := keeper.NewKeeper(
		storeService,
		encCfg.Codec,
		addressCodec,
		authority,
		bankKeeper,
		nil,
	)

	// Initialize params
	if err := k.Params.Set(ctx, types.DefaultParams()); err != nil {
		t.Fatalf("failed to set params: %v", err)
	}

	return &fixture{
		ctx:          ctx,
		keeper:       k,
		addressCodec: addressCodec,
		bankKeeper:   bankKeeper,
	}
}
