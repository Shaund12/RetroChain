package types

import "cosmossdk.io/collections"

const (
	ModuleName = "tokenfactory"
	StoreKey   = ModuleName

	RouterKey = ModuleName

	// GovModuleName duplicates the gov module's name to avoid a dependency with x/gov.
	GovModuleName = "gov"
)

var (
	DenomAdminKeyPrefix    = collections.NewPrefix("tf_admin")
	CreatorDenomsKeyPrefix = collections.NewPrefix("tf_creator_denoms")
)
