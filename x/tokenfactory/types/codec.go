package types

import (
	"github.com/cosmos/cosmos-sdk/codec"
	"github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/cosmos/cosmos-sdk/types/msgservice"
)

var (
	ModuleCdc = codec.NewProtoCodec(types.NewInterfaceRegistry())
)

func RegisterLegacyAminoCodec(_ *codec.LegacyAmino) {}
func RegisterCodec(_ *codec.LegacyAmino)            {}

func RegisterInterfaces(registry types.InterfaceRegistry) {
	msgservice.RegisterMsgServiceDesc(registry, &Msg_serviceDesc)
}
