interface PipelineApiKeys {
  chatApiKey: string
  chatBaseUrl: string
  imageApiKey: string
  imageBaseUrl: string
  videoApiKey: string
  videoBaseUrl: string
  chatRateLimitMin: string
  chatRateLimitDay: string
  imageRateLimitMin: string
  imageRateLimitDay: string
  videoRateLimitMin: string
  videoRateLimitDay: string
}

declare module '*.jpg' { const src: string; export default src }
declare module '*.png' { const src: string; export default src }
declare module '*.mp4' { const src: string; export default src }

interface Window {
  electronAPI: {
    getBackendUrl: () => Promise<string>
    invoke: (channel: string, ...args: unknown[]) => Promise<unknown>
    getSettings: () => Promise<Record<string, unknown>>
    saveSettings: (data: Record<string, unknown>) => Promise<boolean>
  }
  __pipelineApiKeys?: PipelineApiKeys
}
