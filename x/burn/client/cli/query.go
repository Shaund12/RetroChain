package cli

import (
	"encoding/json"

	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/flags"
	"github.com/spf13/cobra"

	"retrochain/x/burn/types"
)

func GetQueryCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:                        types.ModuleName,
		Short:                      "Querying commands for the burn module",
		DisableFlagParsing:         true,
		SuggestionsMinimumDistance: 2,
		RunE:                       client.ValidateCmd,
	}

	cmd.AddCommand(getParamsCmd())
	return cmd
}

func getParamsCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "params",
		Short: "Shows the parameters of the module",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			clientCtx, err := client.GetClientQueryContext(cmd)
			if err != nil {
				return err
			}

			bz, _, err := clientCtx.QueryStore(types.ParamsKey.Bytes(), types.StoreKey)
			if err != nil {
				// If unset or unavailable, fall back to defaults.
				out, _ := json.Marshal(types.DefaultParams())
				return clientCtx.PrintString(string(out) + "\n")
			}

			// Stored as JSON (collections codec).
			var p types.Params
			if err := json.Unmarshal(bz, &p); err != nil {
				// If unexpected encoding, still print raw.
				return clientCtx.PrintString(string(bz) + "\n")
			}
			out, _ := json.Marshal(p)
			return clientCtx.PrintString(string(out) + "\n")
		},
	}

	flags.AddQueryFlagsToCmd(cmd)
	return cmd
}
