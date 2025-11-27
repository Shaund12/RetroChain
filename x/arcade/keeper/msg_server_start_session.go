package keeper

import (
	"context"

	"retrochain/x/arcade/types"

	errorsmod "cosmossdk.io/errors"
)

func (k msgServer) StartSession(ctx context.Context, msg *types.MsgStartSession) (*types.MsgStartSessionResponse, error) {
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, errorsmod.Wrap(err, "invalid authority address")
	}

	// TODO: Handle the message

	return &types.MsgStartSessionResponse{}, nil
}
