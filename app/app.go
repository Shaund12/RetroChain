package app

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"

	clienthelpers "cosmossdk.io/client/v2/helpers"
	"cosmossdk.io/core/appmodule"
	"cosmossdk.io/depinject"
	"cosmossdk.io/log"
	math "cosmossdk.io/math"
	"cosmossdk.io/store/rootmulti"
	storetypes "cosmossdk.io/store/types"
	circuitkeeper "cosmossdk.io/x/circuit/keeper"
	upgradekeeper "cosmossdk.io/x/upgrade/keeper"
	upgradetypes "cosmossdk.io/x/upgrade/types"

	wasmkeeper "github.com/CosmWasm/wasmd/x/wasm/keeper"
	wasmtypes "github.com/CosmWasm/wasmd/x/wasm/types"
	abci "github.com/cometbft/cometbft/abci/types"
	dbm "github.com/cosmos/cosmos-db"
	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/flags"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/cosmos/cosmos-sdk/runtime"
	"github.com/cosmos/cosmos-sdk/server"
	"github.com/cosmos/cosmos-sdk/server/api"
	"github.com/cosmos/cosmos-sdk/server/config"
	servertypes "github.com/cosmos/cosmos-sdk/server/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/module"
	"github.com/cosmos/cosmos-sdk/x/auth"
	authkeeper "github.com/cosmos/cosmos-sdk/x/auth/keeper"
	authsims "github.com/cosmos/cosmos-sdk/x/auth/simulation"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	authzkeeper "github.com/cosmos/cosmos-sdk/x/authz/keeper"
	bankkeeper "github.com/cosmos/cosmos-sdk/x/bank/keeper"
	consensuskeeper "github.com/cosmos/cosmos-sdk/x/consensus/keeper"
	distrkeeper "github.com/cosmos/cosmos-sdk/x/distribution/keeper"
	"github.com/cosmos/cosmos-sdk/x/genutil"
	genutiltypes "github.com/cosmos/cosmos-sdk/x/genutil/types"
	govkeeper "github.com/cosmos/cosmos-sdk/x/gov/keeper"
	mintkeeper "github.com/cosmos/cosmos-sdk/x/mint/keeper"
	paramskeeper "github.com/cosmos/cosmos-sdk/x/params/keeper"
	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"
	slashingkeeper "github.com/cosmos/cosmos-sdk/x/slashing/keeper"
	stakingkeeper "github.com/cosmos/cosmos-sdk/x/staking/keeper"
	icacontrollerkeeper "github.com/cosmos/ibc-go/v10/modules/apps/27-interchain-accounts/controller/keeper"
	icahostkeeper "github.com/cosmos/ibc-go/v10/modules/apps/27-interchain-accounts/host/keeper"
	ibctransferkeeper "github.com/cosmos/ibc-go/v10/modules/apps/transfer/keeper"
	ibckeeper "github.com/cosmos/ibc-go/v10/modules/core/keeper"

	"retrochain/docs"
	arcademodulekeeper "retrochain/x/arcade/keeper"
	_ "retrochain/x/arcade/module" // import for side-effects (module registration)
	btcstakekeeper "retrochain/x/btcstake/keeper"
	btcstaketypes "retrochain/x/btcstake/types"
	burnkeeper "retrochain/x/burn/keeper"
	burntypes "retrochain/x/burn/types"
	retrochainkeeper "retrochain/x/retrochain/keeper"
	retrochaintypes "retrochain/x/retrochain/types"
)

const (
	// Name is the name of the application.
	Name = "retrochain"
	// AccountAddressPrefix is the prefix for accounts addresses.
	AccountAddressPrefix = "cosmos"
	// ChainCoinType is the coin type of the chain.
	ChainCoinType = 118

	// wasmUpgradeName is the on-chain upgrade name that adds the wasm store key.
	wasmUpgradeName = "rc1-wasm-v1"
	// burnUpgradeName is the on-chain upgrade that adds the burn module store key.
	burnUpgradeName = "rc1-burn-v1"
	// burnTokenomicsUpgradeName adjusts burn behavior/order to tame inflation.
	burnTokenomicsUpgradeName = "rc1-burn-tokenomics-v1"
	// btcstakeUpgradeName adds the btcstake module store key.
	btcstakeUpgradeName = "rc1-btcstake-v1"
	// combinedUpgradeName is a single upgrade that enables wasm + burn + btcstake in one shot.
	combinedUpgradeName = "rc1-combined-v1"
	// retrochainUpgradeName is the on-chain upgrade that adds the retrochain module store key.
	retrochainUpgradeName = "rc1-retrochain-v1"
	// tokenfactoryUpgradeName is the on-chain upgrade that adds the tokenfactory module store key.
	tokenfactoryUpgradeName = "rc1-tokenfactory-v1"
	// nftfactoryUpgradeName is the on-chain upgrade that adds the nftfactory module store key.
	nftfactoryUpgradeName = "rc1-nftfactory-v1"
	// clawbackUpgradeName moves mistaken funds back to foundation via a software upgrade.
	clawbackUpgradeName = "rc1-clawback-v1"
)

// DefaultNodeHome default home directories for the application daemon
var DefaultNodeHome string

var (
	_ runtime.AppI            = (*App)(nil)
	_ servertypes.Application = (*App)(nil)
)

// App extends an ABCI application, but with most of its parameters exported.
// They are exported for convenience in creating helper functions, as object
// capabilities aren't needed for testing.
type App struct {
	*runtime.App
	legacyAmino       *codec.LegacyAmino
	appCodec          codec.Codec
	txConfig          client.TxConfig
	interfaceRegistry codectypes.InterfaceRegistry

	// keepers
	// only keepers required by the app are exposed
	// the list of all modules is available in the app_config
	AuthKeeper            authkeeper.AccountKeeper
	BankKeeper            bankkeeper.Keeper
	StakingKeeper         *stakingkeeper.Keeper
	SlashingKeeper        slashingkeeper.Keeper
	MintKeeper            mintkeeper.Keeper
	DistrKeeper           distrkeeper.Keeper
	GovKeeper             *govkeeper.Keeper
	UpgradeKeeper         *upgradekeeper.Keeper
	AuthzKeeper           authzkeeper.Keeper
	ConsensusParamsKeeper consensuskeeper.Keeper
	CircuitBreakerKeeper  circuitkeeper.Keeper
	ParamsKeeper          paramskeeper.Keeper
	RetrochainKeeper      retrochainkeeper.Keeper

	// ibc keepers
	IBCKeeper           *ibckeeper.Keeper
	ICAControllerKeeper icacontrollerkeeper.Keeper
	ICAHostKeeper       icahostkeeper.Keeper
	TransferKeeper      ibctransferkeeper.Keeper
	WasmKeeper          wasmkeeper.Keeper
	BurnKeeper          burnkeeper.Keeper
	BtcstakeKeeper      btcstakekeeper.Keeper

	// simulation manager
	sm           *module.SimulationManager
	ArcadeKeeper arcademodulekeeper.Keeper
}

func init() {
	var err error
	clienthelpers.EnvPrefix = Name
	DefaultNodeHome, err = clienthelpers.GetNodeHomeDirectory("." + Name)
	if err != nil {
		panic(err)
	}
}

// AppConfig returns the default app config.
func AppConfig() depinject.Config {
	return depinject.Configs(
		appConfig,
		depinject.Supply(
			// supply custom module basics
			map[string]module.AppModuleBasic{
				genutiltypes.ModuleName: genutil.NewAppModuleBasic(genutiltypes.DefaultMessageValidator),
			},
		),
	)
}

// New returns a reference to an initialized App.
func New(
	logger log.Logger,
	db dbm.DB,
	traceStore io.Writer,
	loadLatest bool,
	appOpts servertypes.AppOptions,
	baseAppOptions ...func(*baseapp.BaseApp),
) *App {
	var (
		app        = &App{}
		appBuilder *runtime.AppBuilder

		// merge the AppConfig and other configuration in one config
		appConfig = depinject.Configs(
			AppConfig(),
			depinject.Supply(
				appOpts, // supply app options
				logger,  // supply logger
				// here alternative options can be supplied to the DI container.
				// those options can be used f.e to override the default behavior of some modules.
				// for instance supplying a custom address codec for not using bech32 addresses.
				// read the depinject documentation and depinject module wiring for more information
				// on available options and how to use them.
			),
		)
	)

	var appModules map[string]appmodule.AppModule
	if err := depinject.Inject(appConfig,
		&appBuilder,
		&appModules,
		&app.appCodec,
		&app.legacyAmino,
		&app.txConfig,
		&app.interfaceRegistry,
		&app.AuthKeeper,
		&app.BankKeeper,
		&app.StakingKeeper,
		&app.SlashingKeeper,
		&app.MintKeeper,
		&app.DistrKeeper,
		&app.GovKeeper,
		&app.UpgradeKeeper,
		&app.AuthzKeeper,
		&app.ConsensusParamsKeeper,
		&app.CircuitBreakerKeeper,
		&app.ParamsKeeper,
		&app.RetrochainKeeper,
		&app.ArcadeKeeper,
		&app.BurnKeeper,
		&app.BtcstakeKeeper,
	); err != nil {
		panic(err)
	}

	// add to default baseapp options

	// build app
	app.App = appBuilder.Build(db, traceStore, baseAppOptions...)

	// register legacy modules (IBC + wasm)
	if err := app.registerIBCModules(appOpts); err != nil {
		panic(err)
	}

	// configure upgrade handlers after module registration
	app.setupUpgradeHandlers(appOpts, db)

	// CosmWasm (wasmd) panics if Params is missing from state. Some chains can end up
	// with the wasm store key added but params never initialized (e.g. store upgrade
	// without a wasm genesis/init). To keep the chain live, defensively initialize
	// default wasm params at PreBlock if missing.
	app.SetPreBlocker(func(ctx sdk.Context, req *abci.RequestFinalizeBlock) (*sdk.ResponsePreBlock, error) {
		paramsOK := true
		func() {
			defer func() {
				if r := recover(); r != nil {
					paramsOK = false
				}
			}()
			_ = app.WasmKeeper.GetParams(ctx)
		}()
		if !paramsOK {
			ctx.Logger().Info("wasm params missing; initializing defaults to keep chain live")
			if err := app.WasmKeeper.SetParams(ctx, wasmtypes.DefaultParams()); err != nil {
				return nil, err
			}
		}
		return app.App.PreBlocker(ctx, req)
	})

	/****  Module Options ****/

	// create the simulation manager and define the order of the modules for deterministic simulations
	overrideModules := map[string]module.AppModuleSimulation{
		authtypes.ModuleName: auth.NewAppModule(app.appCodec, app.AuthKeeper, authsims.RandomGenesisAccounts, nil),
	}
	app.sm = module.NewSimulationManagerFromAppModules(app.ModuleManager.Modules, overrideModules)

	app.sm.RegisterStoreDecoders()

	// A custom InitChainer sets if extra pre-init-genesis logic is required.
	// This is necessary for manually registered modules that do not support app wiring.
	// Manually set the module version map as shown below.
	// The upgrade module will automatically handle de-duplication of the module version map.
	app.SetInitChainer(func(ctx sdk.Context, req *abci.RequestInitChain) (*abci.ResponseInitChain, error) {
		if err := app.UpgradeKeeper.SetModuleVersionMap(ctx, app.ModuleManager.GetVersionMap()); err != nil {
			return nil, err
		}
		return app.App.InitChainer(ctx, req)
	})

	if err := app.Load(loadLatest); err != nil {
		panic(err)
	}

	return app
}

func storeExistsAtLatestVersion(db dbm.DB, storeKey string) bool {
	if db == nil || storeKey == "" {
		return false
	}
	latest := rootmulti.GetLatestVersion(db)
	if latest <= 0 {
		return false
	}
	bz, err := db.Get([]byte(fmt.Sprintf("s/%d", latest)))
	if err != nil || bz == nil {
		return false
	}
	ci := &storetypes.CommitInfo{}
	if err := ci.Unmarshal(bz); err != nil {
		return false
	}
	for _, si := range ci.StoreInfos {
		if si.Name == storeKey {
			return true
		}
	}
	return false
}

func storeExistsOnDisk(homeDir, storeKey string) bool {
	if homeDir == "" || storeKey == "" {
		return false
	}
	dataDir := filepath.Join(homeDir, "data")
	// goleveldb commonly uses <storeKey>.db (directory). Some setups may use a file.
	candidates := []string{
		filepath.Join(dataDir, storeKey+".db"),
		filepath.Join(dataDir, storeKey),
	}
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			return true
		}
	}
	return false
}

func filterMissingStores(homeDir string, db dbm.DB, storeKeys []string) []string {
	missing := make([]string, 0, len(storeKeys))
	for _, k := range storeKeys {
		// Prefer checking the actual app state DB. If commit-info is missing for any
		// reason, fall back to a filesystem existence check.
		exists := storeExistsAtLatestVersion(db, k)
		if !exists {
			exists = storeExistsOnDisk(homeDir, k)
		}
		if !exists {
			missing = append(missing, k)
		}
	}
	return missing
}

// setupUpgradeHandlers wires store additions behind x/upgrade plans.
//
// Important: Some operators may already have store DBs present on disk (e.g. due to
// earlier testing or an older chain layout). In that case, treating those stores as
// "Added" at the upgrade height will panic (initial version mismatch). To be robust,
// only mark a store as Added if it does not already exist on disk.
func (app *App) setupUpgradeHandlers(appOpts servertypes.AppOptions, db dbm.DB) {
	homeDir := ""
	if appOpts != nil {
		if v := appOpts.Get(flags.FlagHome); v != nil {
			if s, ok := v.(string); ok {
				homeDir = s
			}
		}
	}

	wasmStoreUpgrades := storetypes.StoreUpgrades{Added: filterMissingStores(homeDir, db, []string{wasmtypes.StoreKey})}
	burnStoreUpgrades := storetypes.StoreUpgrades{Added: filterMissingStores(homeDir, db, []string{burntypes.StoreKey})}
	btcstakeStoreUpgrades := storetypes.StoreUpgrades{Added: filterMissingStores(homeDir, db, []string{btcstaketypes.StoreKey})}
	combinedStoreUpgrades := storetypes.StoreUpgrades{Added: filterMissingStores(homeDir, db, []string{wasmtypes.StoreKey, burntypes.StoreKey, btcstaketypes.StoreKey})}
	retrochainStoreUpgrades := storetypes.StoreUpgrades{Added: filterMissingStores(homeDir, db, []string{retrochaintypes.StoreKey})}

	setBurnTokenomicsParams := func(ctx sdk.Context) error {
		// Target inflation control: burn 80% of the fee_collector balance each block.
		// NOTE: This only has the intended effect if burn runs BEFORE distribution.
		return app.BurnKeeper.SetParams(ctx, burntypes.Params{
			FeeBurnRate:       math.LegacyNewDecWithPrec(8, 1), // 0.8
			ProvisionBurnRate: math.LegacyNewDecWithPrec(0, 1), // 0.0
		})
	}

	ensureFeeCollectorBurner := func(ctx sdk.Context) error {
		macc := app.AuthKeeper.GetModuleAccount(ctx, authtypes.FeeCollectorName)
		if macc == nil {
			// create it if missing
			app.AuthKeeper.SetModuleAccount(ctx, authtypes.NewEmptyModuleAccount(authtypes.FeeCollectorName, authtypes.Burner))
			return nil
		}

		if macc.HasPermission(authtypes.Burner) {
			return nil
		}

		var baseAcc *authtypes.BaseAccount
		perms := append([]string{}, macc.GetPermissions()...)
		perms = append(perms, authtypes.Burner)

		switch acc := macc.(type) {
		case *authtypes.ModuleAccount:
			baseAcc = acc.BaseAccount
		default:
			// fall back to overwriting via new empty module account
			app.AuthKeeper.SetModuleAccount(ctx, authtypes.NewEmptyModuleAccount(authtypes.FeeCollectorName, perms...))
			return nil
		}

		if baseAcc == nil {
			app.AuthKeeper.SetModuleAccount(ctx, authtypes.NewEmptyModuleAccount(authtypes.FeeCollectorName, perms...))
			return nil
		}

		app.AuthKeeper.SetModuleAccount(ctx, authtypes.NewModuleAccount(baseAcc, authtypes.FeeCollectorName, perms...))
		return nil
	}

	app.UpgradeKeeper.SetUpgradeHandler(wasmUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})

	app.UpgradeKeeper.SetUpgradeHandler(burnUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})

	app.UpgradeKeeper.SetUpgradeHandler(burnTokenomicsUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		sdkCtx := sdk.UnwrapSDKContext(ctx)
		if err := ensureFeeCollectorBurner(sdkCtx); err != nil {
			return vm, err
		}
		if err := setBurnTokenomicsParams(sdkCtx); err != nil {
			return vm, err
		}
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})

	app.UpgradeKeeper.SetUpgradeHandler(btcstakeUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})

	app.UpgradeKeeper.SetUpgradeHandler(combinedUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		sdkCtx := sdk.UnwrapSDKContext(ctx)
		if err := ensureFeeCollectorBurner(sdkCtx); err != nil {
			return vm, err
		}
		if err := setBurnTokenomicsParams(sdkCtx); err != nil {
			return vm, err
		}
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})

	app.UpgradeKeeper.SetUpgradeHandler(retrochainUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})

	// tokenfactory upgrade wiring must only exist in the post-upgrade binary.
	// If the handler is present before the trigger height, the SDK will refuse to run.
	app.registerTokenfactoryUpgradeHandler()
	// nftfactory upgrade wiring must only exist in the post-upgrade binary.
	app.registerNftfactoryUpgradeHandler()
	// clawback upgrade wiring is safe to include pre-upgrade (no store additions).
	app.registerClawbackUpgradeHandler()

	upgradeInfo, err := app.UpgradeKeeper.ReadUpgradeInfoFromDisk()
	if err != nil {
		panic(err)
	}

	switch upgradeInfo.Name {
	case wasmUpgradeName:
		if !app.UpgradeKeeper.IsSkipHeight(upgradeInfo.Height) {
			if len(wasmStoreUpgrades.Added) > 0 {
				app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &wasmStoreUpgrades))
			}
		}
	case burnUpgradeName:
		if !app.UpgradeKeeper.IsSkipHeight(upgradeInfo.Height) {
			if len(burnStoreUpgrades.Added) > 0 {
				app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &burnStoreUpgrades))
			}
		}
	case btcstakeUpgradeName:
		if !app.UpgradeKeeper.IsSkipHeight(upgradeInfo.Height) {
			if len(btcstakeStoreUpgrades.Added) > 0 {
				app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &btcstakeStoreUpgrades))
			}
		}
	case combinedUpgradeName:
		if !app.UpgradeKeeper.IsSkipHeight(upgradeInfo.Height) {
			if len(combinedStoreUpgrades.Added) > 0 {
				app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &combinedStoreUpgrades))
			}
		}
	case retrochainUpgradeName:
		if !app.UpgradeKeeper.IsSkipHeight(upgradeInfo.Height) {
			if len(retrochainStoreUpgrades.Added) > 0 {
				app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &retrochainStoreUpgrades))
			}
		}
	}

	// tokenfactory store-loader wiring is build-tagged (post-upgrade only).
	app.maybeSetTokenfactoryStoreLoader(homeDir, db, upgradeInfo)
	// nftfactory store-loader wiring is build-tagged (post-upgrade only).
	app.maybeSetNftfactoryStoreLoader(homeDir, db, upgradeInfo)
}

// GetSubspace returns a param subspace for a given module name.
func (app *App) GetSubspace(moduleName string) paramstypes.Subspace {
	subspace, _ := app.ParamsKeeper.GetSubspace(moduleName)
	return subspace
}

// LegacyAmino returns App's amino codec.
func (app *App) LegacyAmino() *codec.LegacyAmino {
	return app.legacyAmino
}

// AppCodec returns App's app codec.
func (app *App) AppCodec() codec.Codec {
	return app.appCodec
}

// InterfaceRegistry returns App's InterfaceRegistry.
func (app *App) InterfaceRegistry() codectypes.InterfaceRegistry {
	return app.interfaceRegistry
}

// TxConfig returns App's TxConfig
func (app *App) TxConfig() client.TxConfig {
	return app.txConfig
}

// GetKey returns the KVStoreKey for the provided store key.
func (app *App) GetKey(storeKey string) *storetypes.KVStoreKey {
	kvStoreKey, ok := app.UnsafeFindStoreKey(storeKey).(*storetypes.KVStoreKey)
	if !ok {
		return nil
	}
	return kvStoreKey
}

// SimulationManager implements the SimulationApp interface
func (app *App) SimulationManager() *module.SimulationManager {
	return app.sm
}

// RegisterAPIRoutes registers all application module routes with the provided
// API server.
func (app *App) RegisterAPIRoutes(apiSvr *api.Server, apiConfig config.APIConfig) {
	app.App.RegisterAPIRoutes(apiSvr, apiConfig)
	// Register explorer-friendly routes after base API wiring so the
	// gRPC-Gateway router/client are initialized and usable.
	app.registerCustomAPIRoutes(apiSvr)
	// register swagger API in app.go so that other applications can override easily
	if err := server.RegisterSwaggerAPI(apiSvr.ClientCtx, apiSvr.Router, apiConfig.Swagger); err != nil {
		panic(err)
	}

	// register app's OpenAPI routes.
	docs.RegisterOpenAPIService(Name, apiSvr.Router)
}

// GetMaccPerms returns a copy of the module account permissions
//
// NOTE: This is solely to be used for testing purposes.
func GetMaccPerms() map[string][]string {
	dup := make(map[string][]string)
	for _, perms := range moduleAccPerms {
		dup[perms.GetAccount()] = perms.GetPermissions()
	}

	return dup
}

// BlockedAddresses returns all the app's blocked account addresses.
func BlockedAddresses() map[string]bool {
	result := make(map[string]bool)

	if len(blockAccAddrs) > 0 {
		for _, addr := range blockAccAddrs {
			result[addr] = true
		}
	} else {
		for addr := range GetMaccPerms() {
			result[addr] = true
		}
	}

	return result
}
