package types

import "cosmossdk.io/collections"

const (
	ModuleName = "btcstake"
	StoreKey   = ModuleName
	RouterKey  = ModuleName
	MemStoreKey = "mem_btcstake"
)

var (
	ParamsKey              = collections.NewPrefix("p_btcstake")
	TotalStakedKey         = collections.NewPrefix("t_btcstake")
	RewardIndexKey         = collections.NewPrefix("i_btcstake")
	UndistributedRewardsKey = collections.NewPrefix("u_btcstake")
	StakeKeyPrefix         = collections.NewPrefix("s_btcstake")
	UserIndexKeyPrefix     = collections.NewPrefix("ui_btcstake")
	PendingRewardsKeyPrefix = collections.NewPrefix("pr_btcstake")
)
