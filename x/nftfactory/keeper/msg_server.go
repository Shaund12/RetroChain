package keeper

import (
	"context"
	"strings"

	"cosmossdk.io/collections"
	"cosmossdk.io/x/nft"

	sdk "github.com/cosmos/cosmos-sdk/types"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"retrochain/x/nftfactory/types"
)

type msgServer struct {
	k Keeper
}

var _ types.MsgServer = msgServer{}

func NewMsgServerImpl(k Keeper) types.MsgServer {
	return msgServer{k: k}
}

func (m msgServer) CreateClass(ctx context.Context, msg *types.MsgCreateClass) (*types.MsgCreateClassResponse, error) {
	if msg == nil || strings.TrimSpace(msg.Sender) == "" {
		return nil, status.Error(codes.InvalidArgument, "sender required")
	}
	creatorBytes, err := m.k.addressCodec.StringToBytes(msg.Sender)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid sender address")
	}
	creatorStr, _ := m.k.addressCodec.BytesToString(creatorBytes)

	classID, err := types.BuildClassID(creatorStr, msg.SubId)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}

	if m.k.nftKeeper.HasClass(ctx, classID) {
		return nil, status.Error(codes.AlreadyExists, types.ErrClassAlreadyExists.Error())
	}

	class := nft.Class{
		Id:          classID,
		Name:        msg.Name,
		Symbol:      msg.Symbol,
		Description: msg.Description,
		Uri:         msg.Uri,
		UriHash:     msg.UriHash,
		Data:        nil,
	}
	if err := m.k.nftKeeper.SaveClass(ctx, class); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	if err := m.k.ClassAdmin.Set(ctx, classID, creatorStr); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	if err := m.k.CreatorClasses.Set(ctx, collections.Join(creatorStr, classID), true); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.MsgCreateClassResponse{ClassId: classID}, nil
}

func (m msgServer) Mint(ctx context.Context, msg *types.MsgMint) (*types.MsgMintResponse, error) {
	if msg == nil || strings.TrimSpace(msg.Sender) == "" {
		return nil, status.Error(codes.InvalidArgument, "sender required")
	}
	if strings.TrimSpace(msg.ClassId) == "" {
		return nil, status.Error(codes.InvalidArgument, "class_id required")
	}
	if strings.TrimSpace(msg.Id) == "" {
		return nil, status.Error(codes.InvalidArgument, "id required")
	}

	admin, err := m.k.GetAdmin(ctx, msg.ClassId)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	if admin != msg.Sender {
		return nil, status.Error(codes.PermissionDenied, types.ErrUnauthorized.Error())
	}

	receiver := msg.Receiver
	if strings.TrimSpace(receiver) == "" {
		receiver = msg.Sender
	}
	recvBytes, err := m.k.addressCodec.StringToBytes(receiver)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid receiver")
	}
	recvAddr := sdk.AccAddress(recvBytes)

	token := nft.NFT{
		ClassId: msg.ClassId,
		Id:      msg.Id,
		Uri:     msg.Uri,
		UriHash: msg.UriHash,
		Data:    nil,
	}
	if err := m.k.nftKeeper.Mint(ctx, token, recvAddr); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &types.MsgMintResponse{}, nil
}
