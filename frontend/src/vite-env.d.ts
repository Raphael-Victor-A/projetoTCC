/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base do backend. Padrao: http://localhost:8000 (ver api/client.ts). */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
