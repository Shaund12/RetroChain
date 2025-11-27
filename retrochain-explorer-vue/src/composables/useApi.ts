import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_REST_API_URL || "http://localhost:1317",
  timeout: 10000
});

export function useApi() {
  return api;
}
