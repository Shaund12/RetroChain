package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type swaggerDoc map[string]any

type mergeStats struct {
	FilesRead      int
	FilesMerged    int
	PathsAdded     int
	DefsAdded      int
	ParamsAdded    int
	ResponsesAdded int
	TagsAdded      int
}

func main() {
	var (
		inDir  string
		outFile string
		title  string
		version string
	)
	flag.StringVar(&inDir, "in", "proto", "Input directory to search for *.swagger.json")
	flag.StringVar(&outFile, "out", "docs/static/openapi.json", "Output OpenAPI (Swagger v2) file")
	flag.StringVar(&title, "title", "Retrochain", "Override info.title")
	flag.StringVar(&version, "version", "", "Override info.version (leave empty to keep existing)")
	flag.Parse()

	files, err := findSwaggerFiles(inDir)
	if err != nil {
		fatal(err)
	}
	if len(files) == 0 {
		fatal(fmt.Errorf("no *.swagger.json files found under %q", inDir))
	}

	// Deterministic order.
	sort.Strings(files)

	merged := swaggerDoc{}
	stats := mergeStats{}

	for _, path := range files {
		doc, err := readSwaggerJSON(path)
		if err != nil {
			fatal(fmt.Errorf("read %s: %w", path, err))
		}
		stats.FilesRead++

		// Skip docs that have no paths.
		if countPaths(doc) == 0 {
			continue
		}

		if len(merged) == 0 {
			merged = doc
			stats.FilesMerged++
			continue
		}

		if err := mergeSwagger(merged, doc, &stats); err != nil {
			fatal(fmt.Errorf("merge %s: %w", path, err))
		}
		stats.FilesMerged++
	}

	if len(merged) == 0 {
		fatal(errors.New("no swagger docs with paths were found to merge"))
	}

	ensureInfo(merged, title, version)

	if err := writePrettyJSON(outFile, merged); err != nil {
		fatal(err)
	}

	fmt.Fprintf(os.Stderr, "merged %d/%d swagger files -> %s (paths+%d defs+%d)\n",
		stats.FilesMerged, stats.FilesRead, outFile, stats.PathsAdded, stats.DefsAdded,
	)
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}

func findSwaggerFiles(root string) ([]string, error) {
	var out []string
	walkRoot := root
	// If invoked from repo root, keep relative paths stable.
	if strings.HasPrefix(walkRoot, "./") {
		walkRoot = strings.TrimPrefix(walkRoot, "./")
	}

	err := filepath.WalkDir(walkRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if strings.HasSuffix(path, ".swagger.json") {
			out = append(out, path)
		}
		return nil
	})
	return out, err
}

func readSwaggerJSON(path string) (swaggerDoc, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc swaggerDoc
	if err := json.Unmarshal(b, &doc); err != nil {
		return nil, err
	}
	return doc, nil
}

func writePrettyJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}

func countPaths(doc swaggerDoc) int {
	paths, _ := doc["paths"].(map[string]any)
	if paths == nil {
		return 0
	}
	return len(paths)
}

func ensureInfo(doc swaggerDoc, title, version string) {
	info, _ := doc["info"].(map[string]any)
	if info == nil {
		info = map[string]any{}
		doc["info"] = info
	}
	if title != "" {
		info["title"] = title
	}
	if version != "" {
		info["version"] = version
	}
}

func mergeSwagger(dst, src swaggerDoc, stats *mergeStats) error {
	// Enforce swagger: "2.0" consistency if present.
	if dv, ok := dst["swagger"].(string); ok {
		if sv, ok := src["swagger"].(string); ok && sv != dv {
			return fmt.Errorf("swagger version mismatch: dst=%q src=%q", dv, sv)
		}
	}

	// Merge selected top-level objects.
	mergeMapOfObjects("paths", dst, src, stats)
	mergeMapOfObjects("definitions", dst, src, stats)
	mergeMapOfObjects("parameters", dst, src, stats)
	mergeMapOfObjects("responses", dst, src, stats)

	mergeTags(dst, src, stats)
	mergeSimpleIfMissing(dst, src, "consumes")
	mergeSimpleIfMissing(dst, src, "produces")
	mergeSimpleIfMissing(dst, src, "schemes")
	mergeSimpleIfMissing(dst, src, "host")
	mergeSimpleIfMissing(dst, src, "basePath")
	mergeSimpleIfMissing(dst, src, "securityDefinitions")
	mergeSimpleIfMissing(dst, src, "security")

	return nil
}

func mergeSimpleIfMissing(dst, src swaggerDoc, key string) {
	if _, ok := dst[key]; ok {
		return
	}
	if v, ok := src[key]; ok {
		dst[key] = v
	}
}

func mergeMapOfObjects(key string, dst, src swaggerDoc, stats *mergeStats) {
	srcMap, _ := src[key].(map[string]any)
	if srcMap == nil {
		return
	}

	dstMap, _ := dst[key].(map[string]any)
	if dstMap == nil {
		dstMap = map[string]any{}
		dst[key] = dstMap
	}

	for k, v := range srcMap {
		if _, exists := dstMap[k]; exists {
			continue
		}
		dstMap[k] = v
		switch key {
		case "paths":
			stats.PathsAdded++
		case "definitions":
			stats.DefsAdded++
		case "parameters":
			stats.ParamsAdded++
		case "responses":
			stats.ResponsesAdded++
		}
	}
}

func mergeTags(dst, src swaggerDoc, stats *mergeStats) {
	srcTags, ok := src["tags"].([]any)
	if !ok || len(srcTags) == 0 {
		return
	}

	dstTags, _ := dst["tags"].([]any)
	existing := map[string]struct{}{}
	for _, t := range dstTags {
		m, _ := t.(map[string]any)
		name, _ := m["name"].(string)
		if name != "" {
			existing[name] = struct{}{}
		}
	}

	for _, t := range srcTags {
		m, _ := t.(map[string]any)
		name, _ := m["name"].(string)
		if name == "" {
			continue
		}
		if _, ok := existing[name]; ok {
			continue
		}
		dstTags = append(dstTags, t)
		existing[name] = struct{}{}
		stats.TagsAdded++
	}

	if len(dstTags) > 0 {
		dst["tags"] = dstTags
	}
}
