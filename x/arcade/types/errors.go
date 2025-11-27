package types

import (
	"github.com/cosmos/cosmos-sdk/types/errors"
)

var (
	ErrInvalidRequest   = errors.Register(ModuleName, 1, "invalid request")
	ErrNotFound         = errors.Register(ModuleName, 2, "not found")
	ErrUnauthorized     = errors.Register(ModuleName, 3, "unauthorized")
	ErrInsufficientFund = errors.Register(ModuleName, 4, "insufficient funds or credits")
	ErrLimitExceeded    = errors.Register(ModuleName, 5, "limit exceeded")
)
