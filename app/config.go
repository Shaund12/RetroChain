package app

import sdk "github.com/cosmos/cosmos-sdk/types"

func init() {
	// Set bond denom
	sdk.DefaultBondDenom = "uretro"

	// Set address prefixes
	accountPubKeyPrefix := AccountAddressPrefix + "pub"
	validatorAddressPrefix := AccountAddressPrefix + "valoper"
	validatorPubKeyPrefix := AccountAddressPrefix + "valoperpub"
	consNodeAddressPrefix := AccountAddressPrefix + "valcons"
	consNodePubKeyPrefix := AccountAddressPrefix + "valconspub"

	// Set and seal config
	config := sdk.GetConfig()
	// Explicitly set BIP44 purpose/coin path to keep wallets aligned with the chain's coin type.
	config.SetPurpose(sdk.Purpose)
	config.SetFullFundraiserPath(sdk.FullFundraiserPath)
	config.SetCoinType(ChainCoinType)
	config.SetBech32PrefixForAccount(AccountAddressPrefix, accountPubKeyPrefix)
	config.SetBech32PrefixForValidator(validatorAddressPrefix, validatorPubKeyPrefix)
	config.SetBech32PrefixForConsensusNode(consNodeAddressPrefix, consNodePubKeyPrefix)
	config.Seal()
}
