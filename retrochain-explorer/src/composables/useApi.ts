import axios from "axios";
import { useNetwork } from "./useNetwork";

// Resolve a base URL that avoids mixed content when the app is under HTTPS.
function resolveBaseUrl() {
  const envBase = import.meta.env.VITE_REST_API_URL as string | undefined;
  const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";

  // If we are on HTTPS and the env base is insecure HTTP, force relative '/api'
  if (isHttps) {
    if (!envBase) return "/api";
    const lower = envBase.toLowerCase();
    if (lower.startsWith("http://")) return "/api"; // avoid mixed content
    return envBase; // https:// or relative path
  }

  // Non-HTTPS page: use env or default relative path (assumed proxy in front)
  return envBase || "/api";
}

const { restBase } = useNetwork();
const api = axios.create({
  baseURL: restBase.value || resolveBaseUrl(),
  timeout: 10000
});

// Indexer read API (separate from chain REST on purpose).
function resolveIndexerBaseUrl() {
  const envBase = (import.meta.env.VITE_INDEXER_API_URL as string | undefined)?.trim();
  return envBase || "";
}

const indexerApi = axios.create({
  baseURL: resolveIndexerBaseUrl(),
  timeout: 10000
});

// react to network changes
// Note: axios instance baseURL can be updated
try {
  const stopWatch = (() => {
    const unwatch = (restBase as any).effect?.(() => {
      api.defaults.baseURL = restBase.value || resolveBaseUrl();
    }) || null;
    return () => unwatch && unwatch();
  })();
} catch {}

export function useApi() {
  return api;
}

export function useIndexerApi() {
  return indexerApi;
}

export function isIndexerEnabled() {
  const base = (indexerApi.defaults.baseURL || "").trim();
  return !!base;
}
