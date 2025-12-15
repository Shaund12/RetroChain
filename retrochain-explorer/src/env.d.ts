/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_INDEXER_API_URL?: string;
  readonly VITE_REST_API_URL?: string;
  readonly VITE_RPC_URL?: string;
  readonly VITE_RPC_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
