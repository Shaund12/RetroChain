package nftfactory

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"

	"retrochain/x/nftfactory/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		Query: &autocliv1.ServiceCommandDescriptor{
			Service: types.Query_serviceDesc.ServiceName,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "ClassAuthorityMetadata",
					Use:       "class-authority-metadata",
					Short:     "Shows the admin for an nftfactory class",
				},
				{
					RpcMethod:      "ClassesFromCreator",
					Use:            "classes-from-creator [creator]",
					Short:          "Lists nftfactory classes created by a creator",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "creator"}},
				},
			},
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service: types.Msg_serviceDesc.ServiceName,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod:      "CreateClass",
					Use:            "create-class [sub-id]",
					Short:          "Create a new NFT class under the sender (nft/<sender>/<sub-id>)",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "sub_id"}},
				},
				{
					RpcMethod:      "Mint",
					Use:            "mint [class-id] [id]",
					Short:          "Mint an NFT into a class (admin only)",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "class_id"}, {ProtoField: "id"}},
				},
			},
		},
	}
}
