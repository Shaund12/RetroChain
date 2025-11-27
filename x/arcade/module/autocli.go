package arcade

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"

	"retrochain/x/arcade/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		Query: &autocliv1.ServiceCommandDescriptor{
			Service: types.Query_serviceDesc.ServiceName,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "Params",
					Use:       "params",
					Short:     "Shows the parameters of the module",
				},
				// this line is used by ignite scaffolding # autocli/query
			},
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service:              types.Msg_serviceDesc.ServiceName,
			EnhanceCustomCommand: true, // only required if you want to use the custom command
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "UpdateParams",
					Skip:      true, // skipped because authority gated
				},
				{
					RpcMethod:      "InsertCoin",
					Use:            "insert-coin [credits] [game-id]",
					Short:          "Send a insert-coin tx",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "credits"}, {ProtoField: "game_id"}},
				},
				{
					RpcMethod:      "SubmitScore",
					Use:            "submit-score [session-id] [score]",
					Short:          "Send a submit-score tx",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "session_id"}, {ProtoField: "score"}},
				},
				{
					RpcMethod:      "StartSession",
					Use:            "start-session [game-id]",
					Short:          "Send a start-session tx",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "game_id"}},
				},
				// this line is used by ignite scaffolding # autocli/tx
			},
		},
	}
}
