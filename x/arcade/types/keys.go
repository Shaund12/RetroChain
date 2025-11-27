package types

const (
	// ModuleName defines the module name
	ModuleName = "arcade"

	// StoreKey defines the primary module store key
	StoreKey = ModuleName

	// RouterKey is the message route for the module
	RouterKey = ModuleName

	// MemStoreKey defines the in-memory store key
	MemStoreKey = "mem_arcade"
)

// KeyPrefix returns a key prefix from a string
func KeyPrefix(p string) []byte { return []byte(p) }
