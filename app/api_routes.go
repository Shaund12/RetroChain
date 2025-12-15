package app

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/cosmos/gogoproto/proto"
	"github.com/cosmos/cosmos-sdk/server/api"
	query "github.com/cosmos/cosmos-sdk/types/query"
	txtypes "github.com/cosmos/cosmos-sdk/types/tx"
	"github.com/grpc-ecosystem/grpc-gateway/runtime"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	arcadetypes "retrochain/x/arcade/types"
	btcstaketypes "retrochain/x/btcstake/types"
)

// registerCustomAPIRoutes mounts convenience HTTP routes behind the /api prefix
// so the explorer can call arcade queries and a simple recent-txs endpoint
// without having to know the gRPC-Gateway base paths.
func (app *App) registerCustomAPIRoutes(apiSvr *api.Server) {
	router := apiSvr.Router
	clientCtx := apiSvr.ClientCtx

	// gatewayHandler is the handler that serves gRPC-Gateway routes.
	// We prefer the server-provided router, but fall back to a locally-registered mux when needed.
	var gatewayHandler http.Handler = apiSvr.GRPCGatewayRouter
	if gatewayHandler == nil {
		gwMux := runtime.NewServeMux()
		var anyOK bool
		if err := arcadetypes.RegisterQueryHandlerClient(clientCtx.CmdContext, gwMux, arcadetypes.NewQueryClient(clientCtx)); err != nil {
			app.Logger().Error("arcade query gateway unavailable", "err", err)
		} else {
			anyOK = true
		}
		if err := btcstaketypes.RegisterQueryHandlerClient(clientCtx.CmdContext, gwMux, btcstaketypes.NewQueryClient(clientCtx)); err != nil {
			app.Logger().Error("btcstake query gateway unavailable", "err", err)
		} else {
			anyOK = true
		}
		if anyOK {
			gatewayHandler = gwMux
		}
	}

	apiGatewayHandler := gatewayHandler
	if apiGatewayHandler != nil {
		apiGatewayHandler = http.StripPrefix("/api", apiGatewayHandler)
	}

	// Compatibility: some clients encode repeated query params as `events[]`.
	// grpc-gateway is strict about query param naming for repeated fields, so the
	// default endpoint can fail with `query cannot be empty`.
	//
	// We proxy the GET endpoint directly to the gRPC tx service to accept both
	// `events` and `events[]` encodings.
	router.Handle("/cosmos/tx/v1beta1/txs", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			if gatewayHandler != nil {
				gatewayHandler.ServeHTTP(w, r)
				return
			}
			http.Error(w, "gateway unavailable", http.StatusServiceUnavailable)
			return
		}

		writeRawJSON := func(obj any) {
			bz, err := json.Marshal(obj)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write(bz)
		}

		writeProtoJSON := func(msg proto.Message) {
			bz, err := clientCtx.Codec.MarshalJSON(msg)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write(bz)
		}

		if clientCtx.GRPCClient == nil {
			http.Error(w, "gRPC client unavailable", http.StatusServiceUnavailable)
			return
		}

		q := r.URL.Query()
		events := append([]string{}, q["events"]...)
		events = append(events, q["events[]"]...)
		queryStr := q.Get("query")
		if queryStr == "" && len(events) > 0 {
			// Cosmos SDK v0.53 prefers `query` (Tendermint TxSearch syntax).
			// Many clients still send repeated `events` params; join them with AND.
			queryStr = strings.Join(events, " AND ")
		}
		if queryStr == "" {
			w.WriteHeader(http.StatusBadRequest)
			writeRawJSON(map[string]any{"code": int32(codes.InvalidArgument), "message": "query cannot be empty", "details": []any{}})
			return
		}

		orderBy := txtypes.OrderBy_ORDER_BY_DESC
		switch q.Get("order_by") {
		case "ORDER_BY_ASC":
			orderBy = txtypes.OrderBy_ORDER_BY_ASC
		case "ORDER_BY_DESC", "":
			orderBy = txtypes.OrderBy_ORDER_BY_DESC
		}

		limit := uint64(20)
		if s := q.Get("limit"); s != "" {
			if v, err := strconv.ParseUint(s, 10, 64); err == nil {
				limit = v
			}
		}
		if s := q.Get("pagination.limit"); s != "" {
			if v, err := strconv.ParseUint(s, 10, 64); err == nil {
				limit = v
			}
		}
		if limit > 100 {
			limit = 100
		}
		offset := uint64(0)
		if s := q.Get("pagination.offset"); s != "" {
			if v, err := strconv.ParseUint(s, 10, 64); err == nil {
				offset = v
			}
		}
		page := uint64(0)
		if s := q.Get("page"); s != "" {
			if v, err := strconv.ParseUint(s, 10, 64); err == nil {
				page = v
			}
		} else if limit > 0 {
			page = (offset / limit) + 1
		}
		countTotal := false
		if s := q.Get("pagination.count_total"); s != "" {
			countTotal = s == "true" || s == "1"
		}

		txClient := txtypes.NewServiceClient(clientCtx.GRPCClient)
		resp, err := txClient.GetTxsEvent(r.Context(), &txtypes.GetTxsEventRequest{
			Query:   queryStr,
			OrderBy: orderBy,
			Page:    page,
			Limit:   limit,
			Pagination: &query.PageRequest{
				Limit:      limit,
				Offset:     offset,
				CountTotal: countTotal,
			},
		})
		if err != nil {
			st, ok := status.FromError(err)
			if ok {
				// Mirror grpc-gateway-ish error payload for the frontend.
				payload := map[string]any{"code": int32(st.Code()), "message": st.Message(), "details": []any{}}
				switch st.Code() {
				case codes.InvalidArgument:
					w.WriteHeader(http.StatusBadRequest)
				default:
					w.WriteHeader(http.StatusInternalServerError)
				}
				writeRawJSON(payload)
				return
			}
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeProtoJSON(resp)
	}))

	rewritePrefix := func(from, to string, next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if next == nil {
				http.Error(w, "gateway unavailable", http.StatusServiceUnavailable)
				return
			}
			r2 := r.Clone(r.Context())
			r2.URL.Path = strings.Replace(r2.URL.Path, from, to, 1)
			next.ServeHTTP(w, r2)
		})
	}

	// Subrouter under /api to keep routing isolated and avoid recursive strip-prefix
	apiRouter := router.PathPrefix("/api").Subrouter()

	// Expose arcade gRPC-Gateway under /api/retrochain/arcade/v1/*
	if apiGatewayHandler != nil {
		apiRouter.PathPrefix("/retrochain/arcade/v1/").Handler(apiGatewayHandler)
	}
	// Explorer alias: /api/arcade/v1/* -> /api/retrochain/arcade/v1/*
	apiRouter.PathPrefix("/arcade/v1/").Handler(rewritePrefix(
		"/api/arcade/v1/",
		"/api/retrochain/arcade/v1/",
		apiGatewayHandler,
	))

	// Also serve the non-/api alias for deployments that proxy-strip the /api prefix.
	// /arcade/v1/* -> /retrochain/arcade/v1/*
	router.PathPrefix("/arcade/v1/").Handler(rewritePrefix(
		"/arcade/v1/",
		"/retrochain/arcade/v1/",
		gatewayHandler,
	))

	// Expose btcstake gRPC-Gateway under /api/retrochain/btcstake/v1/*
	if apiGatewayHandler != nil {
		apiRouter.PathPrefix("/retrochain/btcstake/v1/").Handler(apiGatewayHandler)
	}
	// Explorer alias: /api/btcstake/v1/* -> /api/retrochain/btcstake/v1/*
	apiRouter.PathPrefix("/btcstake/v1/").Handler(rewritePrefix(
		"/api/btcstake/v1/",
		"/api/retrochain/btcstake/v1/",
		apiGatewayHandler,
	))
	// /btcstake/v1/* -> /retrochain/btcstake/v1/*
	router.PathPrefix("/btcstake/v1/").Handler(rewritePrefix(
		"/btcstake/v1/",
		"/retrochain/btcstake/v1/",
		gatewayHandler,
	))

	// Lightweight recent txs endpoint using gRPC tx service with Tendermint RPC fallback
	recentTxsHandler := func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		limit := uint64(20)
		if lStr := r.URL.Query().Get("limit"); lStr != "" {
			if l, err := strconv.Atoi(lStr); err == nil && l > 0 {
				limit = uint64(l)
			}
		}
		if limit > 100 {
			limit = 100
		}

		writeRawJSON := func(obj any) {
			bz, err := json.Marshal(obj)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write(bz)
		}
		writeProtoJSON := func(msg proto.Message) {
			bz, err := clientCtx.Codec.MarshalJSON(msg)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write(bz)
		}

		// Try gRPC first
		if clientCtx.GRPCClient != nil {
			txClient := txtypes.NewServiceClient(clientCtx.GRPCClient)
			resp, err := txClient.GetTxsEvent(ctx, &txtypes.GetTxsEventRequest{
				Query:   "tm.event='Tx'",
				OrderBy: txtypes.OrderBy_ORDER_BY_DESC,
				Limit:   limit,
			})
			if err == nil {
				writeProtoJSON(resp)
				return
			}
			app.Logger().Error("recent-txs gRPC query failed; falling back to RPC", "err", err)
		}

		// Fallback: Tendermint RPC TxSearch (requires RPC client configured)
		if clientCtx.Client == nil {
			http.Error(w, "RPC client unavailable", http.StatusServiceUnavailable)
			return
		}
		limInt := int(limit)
		page := 1
		res, err := clientCtx.Client.TxSearch(ctx, "tm.event='Tx'", false, &page, &limInt, "")
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadGateway)
			return
		}
		writeRawJSON(res)
	}

	apiRouter.HandleFunc("/recent-txs", recentTxsHandler)
	// Fallback for proxy setups that strip /api before forwarding upstream.
	router.HandleFunc("/recent-txs", recentTxsHandler)
}
