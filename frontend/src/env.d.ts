interface ImportMetaEnv {
  readonly VITE_APP_VERSION: string;
  readonly VITE_API_PROXY_TARGET?: string;
  readonly VITE_DEV_SERVER_PORT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
