package btcstake

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"

	"retrochain/x/btcstake/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		Query: &autocliv1.ServiceCommandDescriptor{
			Service: types.Query_serviceDesc.ServiceName,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{RpcMethod: "Params", Use: "params", Short: "Shows the parameters of the module"},
				{RpcMethod: "Stake", Use: "stake [address]", Short: "Shows the staked BTC amount for an address", PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "address"}}},
				{RpcMethod: "PendingRewards", Use: "pending-rewards [address]", Short: "Shows pending uretro rewards for an address", PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "address"}}},
				{RpcMethod: "Pool", Use: "pool", Short: "Shows pool totals and reward index"},
			},
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service:              types.Msg_serviceDesc.ServiceName,
			EnhanceCustomCommand: true,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{RpcMethod: "UpdateParams", Skip: true},
				{RpcMethod: "Stake", Use: "stake [amount]", Short: "Stake BTC (allowed IBC denom) amount (base units)", PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "amount"}}},
				{RpcMethod: "Unstake", Use: "unstake [amount]", Short: "Unstake BTC amount instantly (base units)", PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "amount"}}},
				{RpcMethod: "ClaimRewards", Use: "claim-rewards", Short: "Claim pending uretro rewards"},
				{RpcMethod: "FundRewards", Use: "fund-rewards [amount]", Short: "Fund uretro rewards pool (base units)", PositionalArgs: []*autocliv1.PositionalArgDescriptor{{ProtoField: "amount"}}},
			},
		},
	}
}
