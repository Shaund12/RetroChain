package app

import (
	"context"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	tmproto "github.com/cometbft/cometbft/proto/tendermint/types"
	"github.com/cosmos/cosmos-sdk/server/api"
	"github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/query"
	"github.com/gorilla/mux"

	wasmtypes "github.com/CosmWasm/wasmd/x/wasm/types"
	icacontrollertypes "github.com/cosmos/ibc-go/v10/modules/apps/27-interchain-accounts/controller/types"
	icahosttypes "github.com/cosmos/ibc-go/v10/modules/apps/27-interchain-accounts/host/types"
	ibctransfertypes "github.com/cosmos/ibc-go/v10/modules/apps/transfer/types"
	ibcclienttypes "github.com/cosmos/ibc-go/v10/modules/core/02-client/types"
	ibcconnectiontypes "github.com/cosmos/ibc-go/v10/modules/core/03-connection/types"
	ibcchanneltypes "github.com/cosmos/ibc-go/v10/modules/core/04-channel/types"

	arcadetypes "retrochain/x/arcade/types"
	btcstaketypes "retrochain/x/btcstake/types"
	burntypes "retrochain/x/burn/types"
	retrochaintypes "retrochain/x/retrochain/types"
)

// registerCustomAPIRoutes mounts explorer-friendly convenience routes.
//
// Key rule: never call module QueryServers directly from HTTP handlers.
// gRPC query methods expect an sdk.Context injected by the gRPC server stack,
// so REST must flow through the gRPC-Gateway + gRPC client.
func (app *App) registerCustomAPIRoutes(apiSvr *api.Server) {
	if apiSvr == nil {
		return
	}

	const (
		defaultListLimit   = 5
		maxListLimit       = 100
		maxArcadeScan      = 10000
		maxSmartQueryBody  = 64 * 1024 // 64 KiB POST bodies
		maxSmartQueryParam = 8 * 1024  // 8 KiB GET/param payloads
	)

	router := apiSvr.Router
	clientCtx := apiSvr.ClientCtx

	// Optional CORS allowlist for browser-based explorers.
	// Cosmos SDK's `enabled-unsafe-cors` is either off or wildcard; this provides a strict allowlist.
	//
	// Set `RETROCHAIN_API_CORS_ORIGINS` (or `API_CORS_ORIGINS`) to a comma-separated list, e.g.
	//   https://retrochain.ddns.net,http://retrochain.ddns.net,http://localhost:5173
	// Use `*` only for local/dev.
	if corsMw := newCORSAllowlistMiddlewareFromEnv(); corsMw != nil {
		router.Use(corsMw)
	}

	serveGateway := func(w http.ResponseWriter, r *http.Request) {
		if apiSvr.GRPCGatewayRouter == nil {
			http.Error(w, "gRPC-Gateway not available (enable [api] and [grpc] in app.toml)", http.StatusServiceUnavailable)
			return
		}
		apiSvr.GRPCGatewayRouter.ServeHTTP(w, r)
	}

	// Ensure key module query handlers are registered on the gRPC-Gateway mux.
	// This is safe to call even if already registered.
	if apiSvr.GRPCGatewayRouter != nil && clientCtx.GRPCClient != nil {
		gw := apiSvr.GRPCGatewayRouter
		ctx := context.Background()

		isAlreadyRegistered := func(err error) bool {
			if err == nil {
				return false
			}
			// grpc-gateway returns errors like "pattern ... already registered" when attempting
			// to register duplicate routes on the same ServeMux.
			s := err.Error()
			return strings.Contains(s, "already registered") || strings.Contains(s, "duplicate")
		}
		logErr := func(msg string, err error) {
			fmt.Println(msg + ": " + err.Error())
		}
		mustRegister := func(err error) {
			if err != nil && !isAlreadyRegistered(err) {
				logErr("failed to register gRPC-gateway route", err)
			}
		}

		// Chain modules
		mustRegister(arcadetypes.RegisterQueryHandlerClient(ctx, gw, arcadetypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(burntypes.RegisterQueryHandlerClient(ctx, gw, burntypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(btcstaketypes.RegisterQueryHandlerClient(ctx, gw, btcstaketypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(retrochaintypes.RegisterQueryHandlerClient(ctx, gw, retrochaintypes.NewQueryClient(clientCtx.GRPCClient)))

		// CosmWasm
		mustRegister(wasmtypes.RegisterQueryHandlerClient(ctx, gw, wasmtypes.NewQueryClient(clientCtx.GRPCClient)))

		// IBC core + apps
		mustRegister(ibcclienttypes.RegisterQueryHandlerClient(ctx, gw, ibcclienttypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(ibcconnectiontypes.RegisterQueryHandlerClient(ctx, gw, ibcconnectiontypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(ibcchanneltypes.RegisterQueryHandlerClient(ctx, gw, ibcchanneltypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(ibctransfertypes.RegisterQueryHandlerClient(ctx, gw, ibctransfertypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(icacontrollertypes.RegisterQueryHandlerClient(ctx, gw, icacontrollertypes.NewQueryClient(clientCtx.GRPCClient)))
		mustRegister(icahosttypes.RegisterQueryHandlerClient(ctx, gw, icahosttypes.NewQueryClient(clientCtx.GRPCClient)))
	}

	// Compatibility: some explorers send tx search filters as events[]=...
	// Normalize those to a single `query` string (required by SDK v0.53+) and
	// then fall through to the standard gRPC-Gateway route.
	router.HandleFunc("/cosmos/tx/v1beta1/txs", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			serveGateway(w, r)
			return
		}

		q := r.URL.Query()

		// If caller provided events/events[] but no query, translate events into query.
		// tx service deprecated `events` but still supports it via `query`.
		if q.Get("query") == "" {
			events := append([]string{}, q["events"]...)
			events = append(events, q["events[]"]...)
			if len(events) > 0 {
				q.Set("query", strings.Join(events, " AND "))
				q.Del("events")
				q.Del("events[]")
			}
		}

		// Explorer compatibility: many clients omit query entirely when they just
		// want the latest tx / total count. Cosmos SDK requires query to be non-empty.
		if q.Get("query") == "" {
			q.Set("query", "tx.height>0")
		}

		r2 := cloneRequestWithQuery(r, q)
		serveGateway(w, r2)
	}).Methods(http.MethodGet)

	// Explorer compatibility: list recent sessions across all players.
	// The gRPC query service only supports /sessions/{id} and /sessions/player/{player}.
	// The explorer UI expects a global list at /arcade/v1/sessions.
	listArcadeSessions := func(w http.ResponseWriter, r *http.Request) {
		limit := uint64(defaultListLimit)
		if raw := r.URL.Query().Get("limit"); raw != "" {
			parsed, err := strconv.ParseUint(raw, 10, 64)
			if err != nil {
				http.Error(w, "invalid limit", http.StatusBadRequest)
				return
			}
			if parsed > 0 {
				limit = parsed
			}
		}
		if limit > maxListLimit {
			limit = maxListLimit
		}

		header := tmproto.Header{Height: app.LastBlockHeight(), Time: time.Now(), ChainID: clientCtx.ChainID}
		sdkCtx := app.BaseApp.NewUncachedContext(false, header)
		ctx := types.WrapSDKContext(sdkCtx)

		var sessions []arcadetypes.GameSession
		var scanned uint64
		err := app.ArcadeKeeper.GameSessions.Walk(ctx, nil, func(_ uint64, data []byte) (bool, error) {
			scanned++
			if scanned > maxArcadeScan {
				return true, nil
			}

			var s arcadetypes.GameSession
			if err := json.Unmarshal(data, &s); err != nil {
				return true, err
			}
			sessions = append(sessions, s)
			sort.Slice(sessions, func(i, j int) bool {
				ti, tj := sessions[i].StartTime, sessions[j].StartTime
				switch {
				case ti == nil && tj == nil:
					return sessions[i].SessionId > sessions[j].SessionId
				case ti == nil:
					return false
				case tj == nil:
					return true
				default:
					if ti.Equal(*tj) {
						return sessions[i].SessionId > sessions[j].SessionId
					}
					return ti.After(*tj)
				}
			})
			if len(sessions) > int(limit) {
				sessions = sessions[:limit]
			}
			return false, nil
		})
		if err != nil {
			http.Error(w, "failed to list sessions", http.StatusInternalServerError)
			return
		}

		resp := struct {
			Sessions    []arcadetypes.GameSession `json:"sessions"`
			Pagination  *query.PageResponse       `json:"pagination,omitempty"`
			BlockHeight int64                     `json:"block_height,omitempty"`
		}{
			Sessions:    sessions,
			Pagination:  &query.PageResponse{Total: scanned},
			BlockHeight: sdkCtx.BlockHeight(),
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}

	// Explorer compatibility: list recent achievements across all players.
	// The gRPC query service only supports /achievements/{player}.
	listArcadeAchievements := func(w http.ResponseWriter, r *http.Request) {
		limit := uint64(defaultListLimit)
		if raw := r.URL.Query().Get("limit"); raw != "" {
			parsed, err := strconv.ParseUint(raw, 10, 64)
			if err != nil {
				http.Error(w, "invalid limit", http.StatusBadRequest)
				return
			}
			if parsed > 0 {
				limit = parsed
			}
		}
		if limit > maxListLimit {
			limit = maxListLimit
		}

		header := tmproto.Header{Height: app.LastBlockHeight(), Time: time.Now(), ChainID: clientCtx.ChainID}
		sdkCtx := app.BaseApp.NewUncachedContext(false, header)
		ctx := types.WrapSDKContext(sdkCtx)

		var achievements []arcadetypes.PlayerAchievement
		var scanned uint64
		err := app.ArcadeKeeper.Achievements.Walk(ctx, nil, func(_ string, ach arcadetypes.PlayerAchievement) (bool, error) {
			scanned++
			if scanned > maxArcadeScan {
				return true, nil
			}

			achievements = append(achievements, ach)
			sort.Slice(achievements, func(i, j int) bool {
				ti, tj := achievements[i].UnlockedAt, achievements[j].UnlockedAt
				if ti == nil && tj == nil {
					if achievements[i].Player == achievements[j].Player {
						return achievements[i].AchievementId < achievements[j].AchievementId
					}
					return achievements[i].Player < achievements[j].Player
				}
				if ti == nil {
					return false
				}
				if tj == nil {
					return true
				}
				if ti.Equal(*tj) {
					// deterministic tiebreaker
					if achievements[i].Player == achievements[j].Player {
						return achievements[i].AchievementId < achievements[j].AchievementId
					}
					return achievements[i].Player < achievements[j].Player
				}
				// newest first
				return ti.After(*tj)
			})
			if len(achievements) > int(limit) {
				achievements = achievements[:limit]
			}
			return false, nil
		})
		if err != nil {
			http.Error(w, "failed to list achievements", http.StatusInternalServerError)
			return
		}

		resp := struct {
			Achievements []arcadetypes.PlayerAchievement `json:"achievements"`
			Pagination   *query.PageResponse             `json:"pagination,omitempty"`
			BlockHeight  int64                           `json:"block_height,omitempty"`
		}{
			Achievements: achievements,
			Pagination:   &query.PageResponse{Total: scanned},
			BlockHeight:  sdkCtx.BlockHeight(),
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}

	// Register the explorer-friendly arcade endpoints for both canonical and short prefixes.
	router.HandleFunc("/retrochain/arcade/v1/sessions", listArcadeSessions).Methods(http.MethodGet)
	router.HandleFunc("/arcade/v1/sessions", listArcadeSessions).Methods(http.MethodGet)
	router.HandleFunc("/retrochain/arcade/v1/achievements", listArcadeAchievements).Methods(http.MethodGet)
	router.HandleFunc("/arcade/v1/achievements", listArcadeAchievements).Methods(http.MethodGet)

	// Arcade alias: some clients expect /arcade/v1/* even if the gateway binding is missing.
	router.PathPrefix("/arcade/v1/").Handler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/retrochain" + r.URL.Path
		serveGateway(w, r2)
	}))

	// CosmWasm v0.53 route compatibility: explorers often call /cosmwasm/wasm/v1/params.
	// In wasmd v0.53, Params is served at /cosmwasm/wasm/v1/codes/params.
	router.HandleFunc("/cosmwasm/wasm/v1/params", func(w http.ResponseWriter, r *http.Request) {
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/cosmwasm/wasm/v1/codes/params"
		serveGateway(w, r2)
	}).Methods(http.MethodGet)

	// CosmWasm route compatibility: some clients use the plural /codes endpoint.
	// wasmd exposes code listing at /cosmwasm/wasm/v1/code.
	router.HandleFunc("/cosmwasm/wasm/v1/codes", func(w http.ResponseWriter, r *http.Request) {
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/cosmwasm/wasm/v1/code"
		serveGateway(w, r2)
	}).Methods(http.MethodGet)
	router.HandleFunc("/cosmwasm/wasm/v1/codes/{code_id:[0-9]+}", func(w http.ResponseWriter, r *http.Request) {
		codeID := mux.Vars(r)["code_id"]
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/cosmwasm/wasm/v1/code/" + codeID
		serveGateway(w, r2)
	}).Methods(http.MethodGet)

	// Secret-style compatibility: some explorers request a contract "code hash".
	// On CosmWasm chains, the closest equivalent is the stored CodeInfo.CodeHash (checksum)
	// for the contract's code_id.
	router.HandleFunc("/cosmwasm/wasm/v1/contract/{address}/code-hash", func(w http.ResponseWriter, r *http.Request) {
		address := mux.Vars(r)["address"]

		header := tmproto.Header{Height: app.LastBlockHeight(), Time: time.Now(), ChainID: clientCtx.ChainID}
		sdkCtx := app.BaseApp.NewUncachedContext(false, header)

		contractAddr, err := types.AccAddressFromBech32(address)
		if err != nil {
			http.Error(w, "invalid contract address", http.StatusBadRequest)
			return
		}
		if !app.WasmKeeper.HasContractInfo(sdkCtx, contractAddr) {
			http.Error(w, "contract not found", http.StatusNotFound)
			return
		}

		contractInfo := app.WasmKeeper.GetContractInfo(sdkCtx, contractAddr)
		if contractInfo == nil {
			http.Error(w, "contract not found", http.StatusNotFound)
			return
		}

		codeInfo := app.WasmKeeper.GetCodeInfo(sdkCtx, contractInfo.CodeID)
		if codeInfo == nil {
			http.Error(w, "code info not found", http.StatusNotFound)
			return
		}

		h := hex.EncodeToString(codeInfo.CodeHash)
		resp := struct {
			CodeHash string `json:"code_hash"`
			DataHash string `json:"data_hash,omitempty"`
			CodeID   uint64 `json:"code_id,omitempty"`
		}{
			CodeHash: h,
			DataHash: h,
			CodeID:   contractInfo.CodeID,
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}).Methods(http.MethodGet)

	// CosmWasm compatibility: many clients POST JSON to /contract/{addr}/smart.
	// gRPC-Gateway serves smart queries as GET with base64 bytes in the path.
	router.HandleFunc("/cosmwasm/wasm/v1/contract/{address}/smart", func(w http.ResponseWriter, r *http.Request) {
		address := mux.Vars(r)["address"]

		var payload []byte
		switch r.Method {
		case http.MethodPost:
			r.Body = http.MaxBytesReader(w, r.Body, maxSmartQueryBody)
			body, err := io.ReadAll(r.Body)
			if err != nil {
				http.Error(w, "failed to read body", http.StatusBadRequest)
				return
			}
			_ = r.Body.Close()
			payload = []byte(strings.TrimSpace(string(body)))
			if len(payload) == 0 {
				http.Error(w, "empty smart query", http.StatusBadRequest)
				return
			}
		case http.MethodGet:
			q := r.URL.Query()
			tooLong := func(name, v string) bool {
				if len(v) > maxSmartQueryParam {
					http.Error(w, fmt.Sprintf("%s too large", name), http.StatusRequestEntityTooLarge)
					return true
				}
				return false
			}
			// Some clients send the JSON as a query param instead of POSTing it.
			// Supported forms:
			// - ?query={...}
			// - ?msg={...}
			// - ?query_data=<base64>
			if raw := strings.TrimSpace(q.Get("query_data")); raw != "" {
				if tooLong("query_data", raw) {
					return
				}
				// assume already base64; keep as-is below
				payload = []byte(raw)
				// Mark with a leading 0 byte to signal "already base64".
				payload = append([]byte{0}, payload...)
				break
			}
			raw := q.Get("query")
			if raw == "" {
				raw = q.Get("msg")
			}
			raw = strings.TrimSpace(raw)
			if raw == "" {
				http.Error(w, "missing smart query (POST JSON body or provide ?query=...)", http.StatusBadRequest)
				return
			}
			if tooLong("query", raw) {
				return
			}
			payload = []byte(raw)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var b64Escaped string
		if len(payload) > 0 && payload[0] == 0 {
			// already base64 from ?query_data
			b64Escaped = url.PathEscape(string(payload[1:]))
		} else {
			b64 := base64.StdEncoding.EncodeToString(payload)
			// bytes-in-path parameters are base64; ensure path-safe encoding.
			b64Escaped = url.PathEscape(b64)
		}

		r2 := r.Clone(r.Context())
		r2.Method = http.MethodGet
		r2.Body = nil
		r2.ContentLength = 0
		r2.URL.Path = "/cosmwasm/wasm/v1/contract/" + address + "/smart/" + b64Escaped
		serveGateway(w, r2)
	}).Methods(http.MethodPost, http.MethodGet)

	// IBC transfer compatibility: some explorers still call /denom_traces even though
	// ibc-go v10 exposes denom trace lookups at /denoms.
	router.HandleFunc("/ibc/apps/transfer/v1/denom_traces", func(w http.ResponseWriter, r *http.Request) {
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/ibc/apps/transfer/v1/denoms"
		serveGateway(w, r2)
	}).Methods(http.MethodGet)
	router.HandleFunc("/ibc/apps/transfer/v1/denom_traces/{hash}", func(w http.ResponseWriter, r *http.Request) {
		hash := mux.Vars(r)["hash"]
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/ibc/apps/transfer/v1/denoms/" + hash
		serveGateway(w, r2)
	}).Methods(http.MethodGet)

	// Some clients still use the legacy v1beta1 prefix.
	router.HandleFunc("/ibc/apps/transfer/v1beta1/denom_traces", func(w http.ResponseWriter, r *http.Request) {
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/ibc/apps/transfer/v1/denoms"
		serveGateway(w, r2)
	}).Methods(http.MethodGet)
	router.HandleFunc("/ibc/apps/transfer/v1beta1/denom_traces/{hash}", func(w http.ResponseWriter, r *http.Request) {
		hash := mux.Vars(r)["hash"]
		r2 := r.Clone(r.Context())
		r2.URL.Path = "/ibc/apps/transfer/v1/denoms/" + hash
		serveGateway(w, r2)
	}).Methods(http.MethodGet)

	// Simple recent txs endpoint used by the explorer.
	// NOTE: nginx often strips the leading /api/ when proxying, so we serve both
	// /api/recent-txs and /recent-txs.
	recentTxsHandler := func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		limit := q.Get("limit")
		if limit == "" {
			limit = "50"
		}
		if _, err := strconv.ParseUint(limit, 10, 64); err != nil {
			http.Error(w, "invalid limit", http.StatusBadRequest)
			return
		}

		q2 := url.Values{}
		q2.Set("query", "tx.height>0")
		q2.Set("order_by", "ORDER_BY_DESC")
		q2.Set("limit", limit)
		q2.Set("page", "1")

		r2 := cloneRequestWithQuery(r, q2)
		r2.URL.Path = "/cosmos/tx/v1beta1/txs"
		router.ServeHTTP(w, r2)
	}
	router.HandleFunc("/api/recent-txs", recentTxsHandler).Methods(http.MethodGet)
	router.HandleFunc("/recent-txs", recentTxsHandler).Methods(http.MethodGet)

	// Convenience alias: /api/* -> /* (keeps explorer simple).
	router.PathPrefix("/api/").Handler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r2 := r.Clone(r.Context())
		r2.URL.Path = strings.TrimPrefix(r.URL.Path, "/api")
		if r2.URL.Path == "" {
			r2.URL.Path = "/"
		}
		router.ServeHTTP(w, r2)
	}))

	// (Optional) keep mux import used even if build tags change.
	_ = mux.NewRouter
}

func newCORSAllowlistMiddlewareFromEnv() mux.MiddlewareFunc {
	raw := strings.TrimSpace(os.Getenv("RETROCHAIN_API_CORS_ORIGINS"))
	if raw == "" {
		raw = strings.TrimSpace(os.Getenv("API_CORS_ORIGINS"))
	}
	if raw == "" {
		return nil
	}

	allowed := map[string]struct{}{}
	allowAll := false
	for _, part := range strings.Split(raw, ",") {
		o := strings.TrimSpace(part)
		if o == "" {
			continue
		}
		if o == "*" {
			allowAll = true
			continue
		}
		allowed[o] = struct{}{}
	}

	allowHeaders := "Origin,Accept,Content-Type,Authorization,X-Requested-With"
	allowMethods := "GET,POST,PUT,PATCH,DELETE,OPTIONS"

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := r.Header.Get("Origin")
			if origin != "" {
				if allowAll {
					w.Header().Set("Access-Control-Allow-Origin", "*")
				} else {
					if _, ok := allowed[origin]; ok {
						w.Header().Set("Access-Control-Allow-Origin", origin)
						w.Header().Add("Vary", "Origin")
					}
				}
				w.Header().Set("Access-Control-Allow-Methods", allowMethods)
				w.Header().Set("Access-Control-Allow-Headers", allowHeaders)
			}

			// Short-circuit CORS preflight.
			if r.Method == http.MethodOptions {
				w.WriteHeader(http.StatusNoContent)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

func cloneRequestWithQuery(r *http.Request, q url.Values) *http.Request {
	r2 := r.Clone(r.Context())
	if r2.URL == nil {
		return r2
	}
	r2.URL.RawQuery = q.Encode()
	return r2
}

// Ensure time is referenced (gogoproto stdtime fields) even if build tags change.
var _ = time.Time{}
