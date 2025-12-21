package keeper

import (
	"bytes"
	"context"

	"cosmossdk.io/errors"

	"retrochain/x/burn/types"
)

func (s msgServer) UpdateParams(ctx context.Context, req *types.MsgUpdateParams) (*types.MsgUpdateParamsResponse, error) {
	if req == nil {
		return nil, errors.Wrap(types.ErrInvalidSigner, "empty request")
	}

	signer, err := s.addressCodec.StringToBytes(req.Authority)
	if err != nil {
		return nil, errors.Wrap(types.ErrInvalidSigner, "invalid authority address")
	}

	if !bytes.Equal(signer, s.GetAuthority()) {
		return nil, errors.Wrap(types.ErrInvalidSigner, "unauthorized")
	}

	if err := req.Params.Validate(); err != nil {
		return nil, err
	}

	if err := s.SetParams(ctx, req.Params); err != nil {
		return nil, err
	}

	return &types.MsgUpdateParamsResponse{}, nil
}
