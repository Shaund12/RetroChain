package types

import "cosmossdk.io/collections"

const (
	ModuleName = "nftfactory"
	StoreKey   = ModuleName
	RouterKey  = ModuleName

	// GovModuleName duplicates the gov module's name to avoid a dependency with x/gov.
	GovModuleName = "gov"
)

var (
	ClassAdminKeyPrefix     = collections.NewPrefix("nf_admin")
	CreatorClassesKeyPrefix = collections.NewPrefix("nf_creator_classes")
)
