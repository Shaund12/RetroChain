package types

import "cosmossdk.io/collections"

const (
    // ModuleName defines the module name
    ModuleName = "burn"

    // StoreKey defines the primary module store key
    StoreKey = ModuleName

    // RouterKey is the message route for the module
    RouterKey = ModuleName

    // MemStoreKey defines the in-memory store key
    MemStoreKey = "mem_burn"

    // GovModuleName duplicates the gov module's name to avoid a dependency with x/gov.
    // It should be synced with the gov module's name if it is ever changed.
    GovModuleName = "gov"
)

var (
    // ParamsKey is the prefix to retrieve Params
    ParamsKey = collections.NewPrefix("p_burn")
)

// KeyPrefix returns a key prefix from a string
func KeyPrefix(p string) []byte { return []byte(p) }