<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <title>{{ .Title }}</title>
        <link rel="stylesheet" type="text/css" href="//unpkg.com/swagger-ui-dist@3.40.0/swagger-ui.css" />
        <link rel="icon" type="image/png" href="//unpkg.com/swagger-ui-dist@3.40.0/favicon-16x16.png" />
    </head>
    <body>
      <div id="retrochain-docs-intro" style="padding: 12px 16px;">
        <h2 style="margin: 0 0 8px 0;">API docs</h2>
        <p style="margin: 0 0 8px 0;">
          These docs expose Retrochain module REST routes plus the Cosmos SDK REST surface.
          If you are behind a reverse-proxy that mounts the node under <code>/api/</code>, use the <code>/api</code> version of these URLs.
        </p>
        <p style="margin: 0 0 8px 0;">
          <strong>Common patterns</strong>:
          Query endpoints are <code>GET</code>. Transactions are submitted via <code>POST /cosmos/tx/v1beta1/txs</code> and must include <code>tx_bytes</code> (base64-encoded <code>TxRaw</code>).
        </p>
      </div>
        <div id="swagger-ui"></div>

        <script src="//unpkg.com/swagger-ui-dist@3.40.0/swagger-ui-bundle.js"></script>
        <script>
            // Init Swagger UI with selectable specs (Retrochain + Cosmos SDK)
            window.onload = function() {
              const specs = [
                { name: "Retrochain", url: "{{ .OpenAPI }}" },
                { name: "Cosmos SDK", url: "{{ .CosmosAPI }}" },
              ];
              window.ui = SwaggerUIBundle({
                urls: specs,
                urlsPrimaryName: "Retrochain",
                dom_id: "#swagger-ui",
                deepLinking: true,
                layout: "BaseLayout",
              });
            }
        </script>
    </body>
</html>
