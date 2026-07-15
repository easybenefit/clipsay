import { create } from 'zustand'
import { DEFAULT_SIZE_MAP } from '../sizeConfig'

export interface ModelPreset {
  model: string
  apiKey: string
  baseUrl: string
  rateLimitMin: string
  rateLimitDay: string
}

interface SettingsState {
  chat: ModelPreset
  image: ModelPreset
  video: ModelPreset
  imageSize: string
  sizeMap: Record<string, string>
  loaded: boolean

  loadFromElectronStore: () => Promise<void>
  saveSettings: () => Promise<void>
  updateSetting: (section: 'chat' | 'image' | 'video', field: string, value: string) => void
  setImageSize: (size: string) => void
  setSizeMap: (map: Record<string, string>) => void
}

const CHAT_PRESETS: ModelPreset[] = [
  { model: 'agnes-2.0-flash', apiKey: 'sk-Bz6paVfMyDYHfWGoEVPBMXz2zMy6RWbMBRSxFsjr9J6Ollud', baseUrl: 'https://apihub.agnes-ai.com/v1', rateLimitMin: '50', rateLimitDay: '2000' },
  { model: 'gemini-2.5-flash-001', apiKey: '', baseUrl: 'https://generativelanguage.googleapis.com', rateLimitMin: '500', rateLimitDay: '2000' },
  { model: 'gpt-4o', apiKey: '', baseUrl: 'https://api.openai.com/v1', rateLimitMin: '500', rateLimitDay: '2000' },
  { model: 'claude-3.5-sonnet', apiKey: '', baseUrl: 'https://api.anthropic.com', rateLimitMin: '500', rateLimitDay: '2000' },
]

const IMAGE_PRESETS: ModelPreset[] = [
  { model: 'agnes-image-2.1-flash', apiKey: 'sk-Bz6paVfMyDYHfWGoEVPBMXz2zMy6RWbMBRSxFsjr9J6Ollud', baseUrl: 'https://apihub.agnes-ai.com/v1', rateLimitMin: '10', rateLimitDay: '500' },
  { model: 'imagen-3.0', apiKey: '', baseUrl: 'https://...', rateLimitMin: '10', rateLimitDay: '500' },
  { model: 'dall-e-3', apiKey: '', baseUrl: 'https://api.openai.com/v1', rateLimitMin: '10', rateLimitDay: '500' },
]

const VIDEO_PRESETS: ModelPreset[] = [
  { model: 'agnes-video-v2.0', apiKey: 'sk-Bz6paVfMyDYHfWGoEVPBMXz2zMy6RWbMBRSxFsjr9J6Ollud', baseUrl: 'https://apihub.agnes-ai.com/v1', rateLimitMin: '50', rateLimitDay: '1000' },
  { model: 'veo-2.0', apiKey: '', baseUrl: 'https://...', rateLimitMin: '50', rateLimitDay: '1000' },
  { model: 'kling-1.6', apiKey: '', baseUrl: 'https://...', rateLimitMin: '50', rateLimitDay: '1000' },
]

export const CHAT_OPTIONS = CHAT_PRESETS.map(p => p.model)
export const IMAGE_OPTIONS = IMAGE_PRESETS.map(p => p.model)
export const VIDEO_OPTIONS = VIDEO_PRESETS.map(p => p.model)

export const useSettingsStore = create<SettingsState>((set, get) => ({
  chat: { ...CHAT_PRESETS[0] },
  image: { ...IMAGE_PRESETS[0] },
  video: { ...VIDEO_PRESETS[0] },
  imageSize: '16:9',
  sizeMap: { ...DEFAULT_SIZE_MAP },
  loaded: false,

  loadFromElectronStore: async () => {
    try {
      const s = await window.electronAPI.getSettings()
      if (!s || !Object.keys(s).length) {
        set({ loaded: true })
        return
      }
      set({
        chat: { ...CHAT_PRESETS[0], ...s.chat },
        image: { ...IMAGE_PRESETS[0], ...s.image },
        video: { ...VIDEO_PRESETS[0], ...s.video },
        imageSize: s.imageSize || '16:9',
        sizeMap: s.sizeMap ? { ...DEFAULT_SIZE_MAP, ...s.sizeMap } : { ...DEFAULT_SIZE_MAP },
        loaded: true,
      })
    } catch {
      set({ loaded: true })
    }
  },

  saveSettings: async () => {
    const { chat, image, video, imageSize, sizeMap } = get()
    try {
      await window.electronAPI.saveSettings({ chat, image, video, imageSize, sizeMap })
    } catch { /* ignore */ }
  },

  updateSetting: (section, field, value) => {
    set(state => ({
      [section]: { ...state[section], [field]: value }
    }))
  },

  setImageSize: (imageSize) => {
    set({ imageSize })
    get().saveSettings()
  },

  setSizeMap: (sizeMap) => {
    set({ sizeMap })
  },
}))

export function getSettingsSnapshot() {
  return useSettingsStore.getState()
}
