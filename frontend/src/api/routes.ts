export const APIRoutes = {
  Health: (base: string) => `${base}/health`,
  Query: (base: string) => `${base}/query`,
  MemorySearch: (base: string) => `${base}/memory/search`,
  MemoryGraph: (base: string) => `${base}/memory/graph`,
  NewSession: (base: string) => `${base}/session/new`,
}
