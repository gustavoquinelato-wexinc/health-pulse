/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_TITLE: string
  readonly VITE_ENVIRONMENT: string
  readonly VITE_ETL_SERVICE_URL: string
  readonly VITE_AI_SERVICE_URL: string
  readonly VITE_ENABLE_REAL_TIME: string
  readonly VITE_ENABLE_AI_FEATURES: string
  readonly VITE_ENABLE_ML_FIELDS: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
