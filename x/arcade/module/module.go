package module

import (
	"context"

	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/grpc-ecosystem/grpc-gateway/runtime"

	"retrochain/x/arcade/keeper"
	"retrochain/x/arcade/types"
)

// Module is the config object for the arcade module
type Module struct{}

type AppModule struct {
	cdc    codec.Codec
	keeper keeper.Keeper
}

func NewAppModule(cdc codec.Codec, keeper keeper.Keeper) AppModule {
	return AppModule{
		cdc:    cdc,
		keeper: keeper,
	}
}

func (AppModule) Name() string { return types.ModuleName }

func (AppModule) RegisterInterfaces(registry codectypes.InterfaceRegistry) {
	types.RegisterInterfaces(registry)
}

func (AppModule) RegisterLegacyAminoCodec(cdc *codec.LegacyAmino) {
	types.RegisterLegacyAminoCodec(cdc)
}

func (AppModule) RegisterGRPCGatewayRoutes(clientCtx client.Context, mux *runtime.ServeMux) {
	ctx := context.Background()
	_ = types.RegisterQueryHandlerClient(ctx, mux, types.NewQueryClient(clientCtx))
}

func (am AppModule) IsOnePerModuleType() {}

func (am AppModule) IsAppModule() {}
