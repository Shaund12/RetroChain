package module

import (
	"context"
	"encoding/json"

	"cosmossdk.io/core/appmodule"
	abci "github.com/cometbft/cometbft/abci/types"
	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/module"
	"github.com/grpc-ecosystem/grpc-gateway/runtime"
	"github.com/spf13/cobra"
	"google.golang.org/grpc"

	burncli "retrochain/x/burn/client/cli"
	"retrochain/x/burn/keeper"
	"retrochain/x/burn/types"
)

// AppModuleBasic defines the basic application module used by the burn module.
type AppModuleBasic struct{}

func (AppModuleBasic) Name() string { return types.ModuleName }

func (AppModuleBasic) RegisterLegacyAminoCodec(_ *codec.LegacyAmino) {}

func (AppModuleBasic) DefaultGenesis(cdc codec.JSONCodec) json.RawMessage {
	bz, _ := json.Marshal(types.DefaultParams())
	return bz
}

func (AppModuleBasic) ValidateGenesis(_ codec.JSONCodec, _ client.TxEncodingConfig, bz json.RawMessage) error {
	var p types.Params
	if len(bz) == 0 {
		return nil
	}
	if err := json.Unmarshal(bz, &p); err != nil {
		return err
	}
	return p.Validate()
}

func (AppModuleBasic) RegisterInterfaces(registrar codectypes.InterfaceRegistry) {
	types.RegisterInterfaces(registrar)
}

func (AppModuleBasic) RegisterGRPCGatewayRoutes(clientCtx client.Context, mux *runtime.ServeMux) {
	if err := types.RegisterQueryHandlerClient(clientCtx.CmdContext, mux, types.NewQueryClient(clientCtx)); err != nil {
		panic(err)
	}
}

func (AppModuleBasic) GetTxCmd() *cobra.Command { return nil }

func (AppModuleBasic) GetQueryCmd() *cobra.Command {
	return burncli.GetQueryCmd()
}

// AppModule implements an application module for the burn module.
type AppModule struct {
	AppModuleBasic
	keeper keeper.Keeper
}

// IsAppModule marks compatibility with appmodule wiring helpers.
func (AppModule) IsAppModule() {}

var _ appmodule.AppModule = AppModule{}
var _ module.AppModule = AppModule{}

func NewAppModule(k keeper.Keeper) AppModule {
	return AppModule{keeper: k}
}

func (am AppModule) RegisterServices(registrar grpc.ServiceRegistrar) error {
	types.RegisterMsgServer(registrar, keeper.NewMsgServerImpl(am.keeper))
	types.RegisterQueryServer(registrar, keeper.NewQueryServerImpl(am.keeper))
	return nil
}

func (am AppModule) RegisterGRPCGatewayRoutes(clientCtx client.Context, mux *runtime.ServeMux) {
	if err := types.RegisterQueryHandlerClient(clientCtx.CmdContext, mux, types.NewQueryClient(clientCtx)); err != nil {
		panic(err)
	}
}

func (am AppModule) GetTxCmd() *cobra.Command { return nil }

func (am AppModule) GetQueryCmd() *cobra.Command {
	return burncli.GetQueryCmd()
}

func (am AppModule) InitGenesis(ctx sdk.Context, _ codec.JSONCodec, data json.RawMessage) []abci.ValidatorUpdate {
	var p types.Params
	if len(data) == 0 {
		p = types.DefaultParams()
	} else if err := json.Unmarshal(data, &p); err != nil {
		panic(err)
	}
	if err := am.keeper.InitGenesis(ctx, p); err != nil {
		panic(err)
	}
	return nil
}

func (am AppModule) ExportGenesis(ctx sdk.Context, _ codec.JSONCodec) json.RawMessage {
	p, err := am.keeper.ExportGenesis(ctx)
	if err != nil {
		panic(err)
	}
	bz, _ := json.Marshal(p)
	return bz
}

func (am AppModule) BeginBlock(ctx context.Context) error {
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	am.keeper.BeginBlock(sdkCtx)
	return nil
}

func (am AppModule) EndBlock(context.Context) error { return nil }

func (am AppModule) ConsensusVersion() uint64 { return 1 }

// RegisterInvariants implements the InvariantRegistry.
func (AppModule) RegisterInvariants(_ sdk.InvariantRegistry) {}
