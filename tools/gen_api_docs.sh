#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/docs/api"
COSMOS_SDK_VERSION="v0.53.4"
COSMOS_SDK_SWAGGER_URL="https://raw.githubusercontent.com/cosmos/cosmos-sdk/${COSMOS_SDK_VERSION}/client/docs/swagger-ui/swagger.yaml"

mkdir -p "$OUT"
rm -f "$OUT"/*.swagger.json "$OUT"/swagger.json 2>/dev/null || true
mkdir -p "$ROOT/docs/static"

# Generate merged swagger.json using buf + grpc-gateway openapi plugin
(
  cd "$ROOT/proto"
  buf generate --template buf.gen.swagger.yaml --output "$OUT"
)

# Expect merged file to be named swagger.swagger.json when allow_merge/merge_file_name is set
if [[ -f "$OUT/swagger.swagger.json" ]]; then
  mv "$OUT/swagger.swagger.json" "$OUT/swagger.json"
fi

cp "$OUT/swagger.json" "$ROOT/docs/static/openapi.json"

# Fetch Cosmos SDK full swagger for core chain modules
curl -sSfL "$COSMOS_SDK_SWAGGER_URL" -o "$ROOT/docs/static/cosmos-sdk-swagger.yaml"

echo "Generated API docs: $OUT/swagger.json"
