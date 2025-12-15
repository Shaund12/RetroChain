package docs

import (
	"embed"
	httptemplate "html/template"
	"net/http"
	"strings"

	"github.com/gorilla/mux"
)

const (
	openAPIRelPath = "static/openapi.json"
	cosmosRelPath  = "static/cosmos-sdk-swagger.yaml"
	indexFile      = "template/index.tpl"
	arcadeRoot     = "/arcade/"
)

//go:embed static
var Static embed.FS

//go:embed template
var template embed.FS

//go:embed arcade
var Arcade embed.FS

func RegisterOpenAPIService(appName string, rtr *mux.Router) {
	staticHandler := http.FileServer(http.FS(Static))

	// Serve static OpenAPI assets at root and under /api/* so proxied access works.
	rtr.PathPrefix("/static/").Handler(staticHandler)
	rtr.PathPrefix("/api/static/").Handler(http.StripPrefix("/api", staticHandler))

	rtr.HandleFunc("/", handler(appName, "/"))
	rtr.HandleFunc("/api/", handler(appName, "/api/"))
	rtr.HandleFunc("/api", handler(appName, "/api/"))

	rtr.PathPrefix(arcadeRoot).Handler(http.StripPrefix(arcadeRoot, http.FileServer(http.FS(Arcade))))
}

// handler returns an http handler that serves the OpenAPI console for a given base path.
func handler(title, basePath string) http.HandlerFunc {
	base := normalizeBasePath(basePath)
	openAPIURL := base + openAPIRelPath
	cosmosURL := base + cosmosRelPath

	t, _ := httptemplate.ParseFS(template, indexFile)

	return func(w http.ResponseWriter, req *http.Request) {
		_ = t.Execute(w, struct {
			Title     string
			OpenAPI   string
			CosmosAPI string
		}{
			Title:     title,
			OpenAPI:   openAPIURL,
			CosmosAPI: cosmosURL,
		})
	}
}

func normalizeBasePath(base string) string {
	if base == "" {
		return "/"
	}
	if !strings.HasPrefix(base, "/") {
		base = "/" + base
	}
	if !strings.HasSuffix(base, "/") {
		base += "/"
	}
	return base
}
