#!/usr/bin/env bash
set -euo pipefail

RPC_ADDR=${RPC_ADDR:-http://localhost:26657}
API_ADDR=${API_ADDR:-http://localhost:1317}
GRPC_ADDR=${GRPC_ADDR:-localhost:9090}
GRPC_INSECURE=${GRPC_INSECURE:-true}
TIMEOUT=${TIMEOUT:-5}

pass() { printf "[OK] %s\n" "$*"; }
fail() { printf "[FAIL] %s\n" "$*"; }

http_get() {
  local url=$1
  if curl -s --max-time "$TIMEOUT" "$url" >/tmp/api_check_resp.$$; then
    pass "GET $url" && return 0
  else
    fail "GET $url" && return 1
  fi
}

check_rpc() {
  echo "-- RPC checks ($RPC_ADDR) --"
  http_get "$RPC_ADDR/status"
  http_get "$RPC_ADDR/health"
  http_get "$RPC_ADDR/net_info"
  http_get "$RPC_ADDR/block"
}

check_api() {
  echo "-- REST/gRPC-Gateway checks ($API_ADDR) --"
  http_get "$API_ADDR/cosmos/base/tendermint/v1beta1/blocks/latest"
  http_get "$API_ADDR/cosmos/auth/v1beta1/accounts"
  http_get "$API_ADDR/api/recent-txs" || true
}

check_grpc() {
  echo "-- gRPC checks ($GRPC_ADDR) --"
  if ! command -v grpcurl >/dev/null 2>&1; then
    fail "grpcurl not found; skipping gRPC checks"
    return 0
  fi
  local tlsFlag=--plaintext
  if [ "$GRPC_INSECURE" != "true" ]; then tlsFlag=""; fi
  grpcurl --max-time "$TIMEOUT" $tlsFlag "$GRPC_ADDR" list >/tmp/grpc_list.$$ && pass "grpc reflection/list" || fail "grpc reflection/list"
  grpcurl --max-time "$TIMEOUT" $tlsFlag "$GRPC_ADDR" cosmos.base.tendermint.v1beta1.Service/GetLatestBlock >/tmp/grpc_block.$$ && pass "GetLatestBlock" || fail "GetLatestBlock"
}

check_ports() {
  echo "-- Port availability --"
  local rpc_host_port api_host_port grpc_host_port
  rpc_host_port=${RPC_ADDR#http://}
  rpc_host_port=${rpc_host_port#https://}
  api_host_port=${API_ADDR#http://}
  api_host_port=${api_host_port#https://}
  grpc_host_port=$GRPC_ADDR
  if command -v nc >/dev/null 2>&1; then
    nc -z -w "$TIMEOUT" ${rpc_host_port%/} >/dev/null 2>&1 && pass "RPC port open: $rpc_host_port" || fail "RPC port closed: $rpc_host_port"
    nc -z -w "$TIMEOUT" ${api_host_port%/} >/dev/null 2>&1 && pass "API port open: $api_host_port" || fail "API port closed: $api_host_port"
    nc -z -w "$TIMEOUT" ${grpc_host_port%/} >/dev/null 2>&1 && pass "gRPC port open: $grpc_host_port" || fail "gRPC port closed: $grpc_host_port"
  else
    fail "nc not found; skipping port checks"
  fi
}

check_ports
check_rpc
check_api
check_grpc

echo "Done."
