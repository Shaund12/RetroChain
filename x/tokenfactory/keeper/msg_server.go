package keeper

import (
	"context"
	"strings"

	"cosmossdk.io/collections"

	sdk "github.com/cosmos/cosmos-sdk/types"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"retrochain/x/tokenfactory/types"
)

type msgServer struct {
	k Keeper
}

var _ types.MsgServer = msgServer{}

func NewMsgServerImpl(k Keeper) types.MsgServer {
	return msgServer{k: k}
}

func (m msgServer) CreateDenom(ctx context.Context, msg *types.MsgCreateDenom) (*types.MsgCreateDenomResponse, error) {
	if msg == nil || strings.TrimSpace(msg.Sender) == "" {
		return nil, status.Error(codes.InvalidArgument, "sender required")
	}
	creatorBytes, err := m.k.addressCodec.StringToBytes(msg.Sender)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid sender address")
	}
	creatorStr, _ := m.k.addressCodec.BytesToString(creatorBytes)

	newDenom, err := types.BuildFactoryDenom(creatorStr, msg.Subdenom)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}

	exists, err := m.k.HasDenom(ctx, newDenom)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	if exists {
		return nil, status.Error(codes.AlreadyExists, types.ErrDenomAlreadyExists.Error())
	}

	if err := m.k.DenomAdmin.Set(ctx, newDenom, creatorStr); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	if err := m.k.CreatorDenoms.Set(ctx, collections.Join(creatorStr, newDenom), true); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.MsgCreateDenomResponse{NewDenom: newDenom}, nil
}

func (m msgServer) Mint(ctx context.Context, msg *types.MsgMint) (*types.MsgMintResponse, error) {
	if msg == nil || strings.TrimSpace(msg.Sender) == "" {
		return nil, status.Error(codes.InvalidArgument, "sender required")
	}

	coin, err := sdk.ParseCoinNormalized(msg.Amount)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid amount")
	}
	if !coin.IsPositive() {
		return nil, status.Error(codes.InvalidArgument, "amount must be > 0")
	}

	admin, err := m.k.GetAdmin(ctx, coin.Denom)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	if admin != msg.Sender {
		return nil, status.Error(codes.PermissionDenied, types.ErrUnauthorized.Error())
	}

	mintTo := msg.MintToAddress
	if strings.TrimSpace(mintTo) == "" {
		mintTo = msg.Sender
	}
	toAddrBytes, err := m.k.addressCodec.StringToBytes(mintTo)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid mint_to_address")
	}
	toAddr := sdk.AccAddress(toAddrBytes)

	if err := m.k.bankKeeper.MintCoins(ctx, types.ModuleName, sdk.NewCoins(coin)); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	if err := m.k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, toAddr, sdk.NewCoins(coin)); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.MsgMintResponse{}, nil
}

func (m msgServer) Burn(ctx context.Context, msg *types.MsgBurn) (*types.MsgBurnResponse, error) {
	if msg == nil || strings.TrimSpace(msg.Sender) == "" {
		return nil, status.Error(codes.InvalidArgument, "sender required")
	}

	coin, err := sdk.ParseCoinNormalized(msg.Amount)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid amount")
	}
	if !coin.IsPositive() {
		return nil, status.Error(codes.InvalidArgument, "amount must be > 0")
	}

	admin, err := m.k.GetAdmin(ctx, coin.Denom)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	if admin != msg.Sender {
		return nil, status.Error(codes.PermissionDenied, types.ErrUnauthorized.Error())
	}

	burnFrom := msg.BurnFromAddress
	if strings.TrimSpace(burnFrom) == "" {
		burnFrom = msg.Sender
	}
	fromAddrBytes, err := m.k.addressCodec.StringToBytes(burnFrom)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid burn_from_address")
	}
	fromAddr := sdk.AccAddress(fromAddrBytes)

	if err := m.k.bankKeeper.SendCoinsFromAccountToModule(ctx, fromAddr, types.ModuleName, sdk.NewCoins(coin)); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	if err := m.k.bankKeeper.BurnCoins(ctx, types.ModuleName, sdk.NewCoins(coin)); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.MsgBurnResponse{}, nil
}

func (m msgServer) ChangeAdmin(ctx context.Context, msg *types.MsgChangeAdmin) (*types.MsgChangeAdminResponse, error) {
	if msg == nil || strings.TrimSpace(msg.Sender) == "" {
		return nil, status.Error(codes.InvalidArgument, "sender required")
	}
	if strings.TrimSpace(msg.Denom) == "" {
		return nil, status.Error(codes.InvalidArgument, "denom required")
	}
	if strings.TrimSpace(msg.NewAdmin) == "" {
		return nil, status.Error(codes.InvalidArgument, "new_admin required")
	}

	admin, err := m.k.GetAdmin(ctx, msg.Denom)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	if admin != msg.Sender {
		return nil, status.Error(codes.PermissionDenied, types.ErrUnauthorized.Error())
	}

	if _, err := m.k.addressCodec.StringToBytes(msg.NewAdmin); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid new_admin")
	}
	if err := m.k.DenomAdmin.Set(ctx, msg.Denom, msg.NewAdmin); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &types.MsgChangeAdminResponse{}, nil
}
