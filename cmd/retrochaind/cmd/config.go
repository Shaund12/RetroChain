package cmd

import (
	"time"

	wasmtypes "github.com/CosmWasm/wasmd/x/wasm/types"
	cmtcfg "github.com/cometbft/cometbft/config"
	serverconfig "github.com/cosmos/cosmos-sdk/server/config"
)

// initCometBFTConfig helps to override default CometBFT Config values.
// return cmtcfg.DefaultConfig if no custom configuration is required for the application.
func initCometBFTConfig() *cmtcfg.Config {
	cfg := cmtcfg.DefaultConfig()

	// Allow the hosted explorer frontend to call CometBFT RPC from browsers.
	// Note: CORS origins are scheme-specific.
	cfg.RPC.CORSAllowedOrigins = []string{
		"https://retrochain.ddns.net",
		"http://retrochain.ddns.net",
		"http://localhost:1317",
		"http://127.0.0.1:1317",
	}

	// Explorer/indexer performance: enable tx indexing by default.
	// - "kv" enables /tx_search and event-based queries.
	cfg.TxIndex.Indexer = "kv"

	// Block time: increase default commit timeout (new nodes only).
	// Note: operators can still override this in config.toml under [consensus].
	cfg.Consensus.TimeoutCommit = 6 * time.Second

	// Peer caps: avoid runaway inbound peers on public nodes.
	cfg.P2P.MaxNumInboundPeers = 60
	cfg.P2P.MaxNumOutboundPeers = 20

	// Expose CometBFT metrics by default for ops observability.
	cfg.Instrumentation.Prometheus = true
	cfg.Instrumentation.MaxOpenConnections = 10

	return cfg
}

// initAppConfig helps to override default appConfig template and configs.
// return "", nil if no custom configuration is required for the application.
func initAppConfig() (string, interface{}) {
	type CustomAppConfig struct {
		serverconfig.Config `mapstructure:",squash"`
		Wasm                wasmtypes.NodeConfig `mapstructure:"wasm"`
	}

	// Optionally allow the chain developer to overwrite the SDK's default
	// server config.
	srvCfg := serverconfig.DefaultConfig()
	// Make API docs available by default for fresh nodes.
	// Note: operators can override these in app.toml.
	srvCfg.API.Enable = true
	srvCfg.API.Swagger = true
	// The SDK's default minimum gas price is set to "" (empty value) inside
	// app.toml. If left empty by validators, the node will halt on startup.
	// However, the chain developer can set a default app.toml value for their
	// validators here.
	//
	// In summary:
	// - if you leave srvCfg.MinGasPrices = "", all validators MUST tweak their
	//   own app.toml config,
	// - if you set srvCfg.MinGasPrices non-empty, validators CAN tweak their
	//   own app.toml to override, or use this default value.
	//
	// In tests, we set the min gas prices to 0.
	// srvCfg.MinGasPrices = "0stake"
	srvCfg.MinGasPrices = "0.0025uretro"

	// Basic telemetry with global labels for Prometheus.
	srvCfg.Telemetry.Enabled = true
	srvCfg.Telemetry.ServiceName = "retrochaind"
	srvCfg.Telemetry.EnableHostname = true
	srvCfg.Telemetry.EnableHostnameLabel = true
	srvCfg.Telemetry.EnableServiceLabel = true
	srvCfg.Telemetry.PrometheusRetentionTime = 60
	srvCfg.Telemetry.GlobalLabels = [][]string{
		{"chain_id", "retrochain-mainnet"},
	}

	// Produce snapshots so state sync works out-of-the-box.
	srvCfg.StateSync.SnapshotInterval = 500
	srvCfg.StateSync.SnapshotKeepRecent = 2

	customAppConfig := CustomAppConfig{
		Config: *srvCfg,
		Wasm:   wasmtypes.DefaultNodeConfig(),
	}

	customAppTemplate := serverconfig.DefaultConfigTemplate + wasmtypes.DefaultConfigTemplate()

	return customAppTemplate, customAppConfig
}
