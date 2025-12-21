package keeper

import (
	"context"
	"strings"

	"cosmossdk.io/collections"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"retrochain/x/tokenfactory/types"
)

type queryServer struct {
	k Keeper
}

var _ types.QueryServer = queryServer{}

func NewQueryServerImpl(k Keeper) types.QueryServer {
	return queryServer{k: k}
}

func (q queryServer) DenomAuthorityMetadata(ctx context.Context, req *types.QueryDenomAuthorityMetadataRequest) (*types.QueryDenomAuthorityMetadataResponse, error) {
	if req == nil || strings.TrimSpace(req.Denom) == "" {
		return nil, status.Error(codes.InvalidArgument, "denom required")
	}
	admin, err := q.k.GetAdmin(ctx, req.Denom)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	return &types.QueryDenomAuthorityMetadataResponse{AuthorityMetadata: &types.DenomAuthorityMetadata{Admin: admin}}, nil
}

func (q queryServer) DenomsFromCreator(ctx context.Context, req *types.QueryDenomsFromCreatorRequest) (*types.QueryDenomsFromCreatorResponse, error) {
	if req == nil || strings.TrimSpace(req.Creator) == "" {
		return nil, status.Error(codes.InvalidArgument, "creator required")
	}

	// Simple scan; expected small cardinality.
	denoms := make([]string, 0)
	err := q.k.CreatorDenoms.Walk(ctx, nil, func(key collections.Pair[string, string], _ bool) (bool, error) {
		if key.K1() == req.Creator {
			denoms = append(denoms, key.K2())
		}
		return false, nil
	})
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.QueryDenomsFromCreatorResponse{Denoms: denoms}, nil
}
