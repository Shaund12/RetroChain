package arcade

import (
	"math/rand"

	"github.com/cosmos/cosmos-sdk/types/module"
	simtypes "github.com/cosmos/cosmos-sdk/types/simulation"
	"github.com/cosmos/cosmos-sdk/x/simulation"

	arcadesimulation "retrochain/x/arcade/simulation"
	"retrochain/x/arcade/types"
)

// GenerateGenesisState creates a randomized GenState of the module.
func (AppModule) GenerateGenesisState(simState *module.SimulationState) {
	accs := make([]string, len(simState.Accounts))
	for i, acc := range simState.Accounts {
		accs[i] = acc.Address.String()
	}
	arcadeGenesis := types.GenesisState{
		Params: types.DefaultParams(),
	}
	simState.GenState[types.ModuleName] = simState.Cdc.MustMarshalJSON(&arcadeGenesis)
}

// RegisterStoreDecoder registers a decoder.
func (am AppModule) RegisterStoreDecoder(_ simtypes.StoreDecoderRegistry) {}

// WeightedOperations returns the all the gov module operations with their respective weights.
func (am AppModule) WeightedOperations(simState module.SimulationState) []simtypes.WeightedOperation {
	operations := make([]simtypes.WeightedOperation, 0)
	const (
		opWeightMsgInsertCoin          = "op_weight_msg_arcade"
		defaultWeightMsgInsertCoin int = 100
	)

	var weightMsgInsertCoin int
	simState.AppParams.GetOrGenerate(opWeightMsgInsertCoin, &weightMsgInsertCoin, nil,
		func(_ *rand.Rand) {
			weightMsgInsertCoin = defaultWeightMsgInsertCoin
		},
	)
	operations = append(operations, simulation.NewWeightedOperation(
		weightMsgInsertCoin,
		arcadesimulation.SimulateMsgInsertCoin(am.authKeeper, am.bankKeeper, am.keeper, simState.TxConfig),
	))
	const (
		opWeightMsgSubmitScore          = "op_weight_msg_arcade"
		defaultWeightMsgSubmitScore int = 100
	)

	var weightMsgSubmitScore int
	simState.AppParams.GetOrGenerate(opWeightMsgSubmitScore, &weightMsgSubmitScore, nil,
		func(_ *rand.Rand) {
			weightMsgSubmitScore = defaultWeightMsgSubmitScore
		},
	)
	operations = append(operations, simulation.NewWeightedOperation(
		weightMsgSubmitScore,
		arcadesimulation.SimulateMsgSubmitScore(am.authKeeper, am.bankKeeper, am.keeper, simState.TxConfig),
	))
	const (
		opWeightMsgStartSession          = "op_weight_msg_arcade"
		defaultWeightMsgStartSession int = 100
	)

	var weightMsgStartSession int
	simState.AppParams.GetOrGenerate(opWeightMsgStartSession, &weightMsgStartSession, nil,
		func(_ *rand.Rand) {
			weightMsgStartSession = defaultWeightMsgStartSession
		},
	)
	operations = append(operations, simulation.NewWeightedOperation(
		weightMsgStartSession,
		arcadesimulation.SimulateMsgStartSession(am.authKeeper, am.bankKeeper, am.keeper, simState.TxConfig),
	))

	return operations
}

// ProposalMsgs returns msgs used for governance proposals for simulations.
func (am AppModule) ProposalMsgs(simState module.SimulationState) []simtypes.WeightedProposalMsg {
	return []simtypes.WeightedProposalMsg{}
}
