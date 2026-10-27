/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_MOCK_API?: string;
  readonly VITE_BASEMAP_STYLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
