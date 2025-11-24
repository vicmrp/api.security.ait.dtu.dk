/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MSAL_CLIENT_ID: string
  readonly VITE_MSAL_TENANT_ID: string
  readonly VITE_MSAL_AUTHORITY: string
  readonly VITE_MSAL_REDIRECT_URI: string
  readonly VITE_MSAL_POST_LOGOUT_REDIRECT_URI: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}