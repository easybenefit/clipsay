interface AppSettings {
  chat: {
    model: string
    apiKey: string
    baseUrl: string
    rateLimitMin: string
    rateLimitDay: string
  }
  image: {
    model: string
    apiKey: string
    baseUrl: string
    rateLimitMin: string
    rateLimitDay: string
  }
  video: {
    model: string
    apiKey: string
    baseUrl: string
    rateLimitMin: string
    rateLimitDay: string
  }
  imageSize: string
  sizeMap: Record<string, string>
}

interface ElectronAPI {
  getBackendUrl: () => Promise<string>
  invoke: (channel: string, ...args: unknown[]) => Promise<unknown>
  getSettings: () => Promise<AppSettings>
  saveSettings: (data: AppSettings) => Promise<boolean>
}

interface Window {
  electronAPI: ElectronAPI
}
