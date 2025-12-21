package keeper

import (
	"context"
	"strings"

	"cosmossdk.io/collections"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"retrochain/x/nftfactory/types"
)

type queryServer struct {
	k Keeper
}

var _ types.QueryServer = queryServer{}

func NewQueryServerImpl(k Keeper) types.QueryServer {
	return queryServer{k: k}
}

func (q queryServer) ClassAuthorityMetadata(ctx context.Context, req *types.QueryClassAuthorityMetadataRequest) (*types.QueryClassAuthorityMetadataResponse, error) {
	if req == nil || strings.TrimSpace(req.ClassId) == "" {
		return nil, status.Error(codes.InvalidArgument, "class_id required")
	}
	admin, err := q.k.GetAdmin(ctx, req.ClassId)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	return &types.QueryClassAuthorityMetadataResponse{AuthorityMetadata: &types.ClassAuthorityMetadata{Admin: admin}}, nil
}

func (q queryServer) ClassesFromCreator(ctx context.Context, req *types.QueryClassesFromCreatorRequest) (*types.QueryClassesFromCreatorResponse, error) {
	if req == nil || strings.TrimSpace(req.Creator) == "" {
		return nil, status.Error(codes.InvalidArgument, "creator required")
	}

	classIDs := make([]string, 0)
	err := q.k.CreatorClasses.Walk(ctx, nil, func(key collections.Pair[string, string], _ bool) (bool, error) {
		if key.K1() == req.Creator {
			classIDs = append(classIDs, key.K2())
		}
		return false, nil
	})
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.QueryClassesFromCreatorResponse{ClassIds: classIDs}, nil
}
