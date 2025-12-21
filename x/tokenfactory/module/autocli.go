package tokenfactory

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"

	"retrochain/x/tokenfactory/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		Query: &autocliv1.ServiceCommandDescriptor{
			Service: types.Query_serviceDesc.ServiceName,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "DenomAuthorityMetadata",
					Use:       "denom-authority-metadata",
					Short:     "Shows the admin for a factory denom",
				},
				{
					RpcMethod:      "DenomsFromCreator",
					Use:            "denoms-from-creator [creator]",
					Short:          "Lists factory denoms created by a creator",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "creator"}},
				},
			},
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service: types.Msg_serviceDesc.ServiceName,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod:      "CreateDenom",
					Use:            "create-denom [subdenom]",
					Short:          "Create a new factory denom under the sender",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "subdenom"}},
				},
				{
					RpcMethod:      "Mint",
					Use:            "mint [amount]",
					Short:          "Mint factory tokens (admin only)",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "amount"}},
				},
				{
					RpcMethod:      "Burn",
					Use:            "burn [amount]",
					Short:          "Burn factory tokens (admin only)",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "amount"}},
				},
				{
					RpcMethod:      "ChangeAdmin",
					Use:            "change-admin [denom] [new-admin]",
					Short:          "Change the admin of a factory denom",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "denom"}, {ProtoField: "new_admin"}},
				},
			},
		},
	}
}
