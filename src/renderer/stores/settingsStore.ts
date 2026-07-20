import { create } from 'zustand'
import { BASE } from '../api'
import { DEFAULT_SIZE_MAP } from '../sizeConfig'

interface ModelPreset {
  model: string
  apiKey: string
  baseUrl: string
  rateLimitMin: string
  rateLimitDay: string
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

export interface ModelConfig {
  model: string
  apiKey: string
  baseUrl: string
  rateLimitMin: string
  rateLimitDay: string
}

export interface AppSettings {
  chat: ModelConfig
  image: ModelConfig
  video: ModelConfig
  imageSize: string
  sizeTier: string
  sizeMap: Record<string, string>
}

function makeDefaultSettings(): AppSettings {
  return {
    chat: { ...CHAT_PRESETS[0], rateLimitMin: CHAT_PRESETS[0].rateLimitMin, rateLimitDay: CHAT_PRESETS[0].rateLimitDay },
    image: { ...IMAGE_PRESETS[0], rateLimitMin: IMAGE_PRESETS[0].rateLimitMin, rateLimitDay: IMAGE_PRESETS[0].rateLimitDay },
    video: { ...VIDEO_PRESETS[0], rateLimitMin: VIDEO_PRESETS[0].rateLimitMin, rateLimitDay: VIDEO_PRESETS[0].rateLimitDay },
    imageSize: '16:9',
    sizeTier: '1K',
    sizeMap: { ...DEFAULT_SIZE_MAP },
  }
}

let toastTimer: ReturnType<typeof setTimeout>

interface SettingsState {
  settings: AppSettings
  health: string
  settingsLoaded: boolean
  toast: string | null

  initialize: () => Promise<void>
  setHealth: (health: string) => void
  updateSetting: (section: 'chat' | 'image' | 'video', field: string, value: string) => void
  onModelChange: (section: 'chat' | 'image' | 'video', model: string) => void
  saveSection: (section: 'chat' | 'image' | 'video') => Promise<void>
  setSizeTier: (tier: string) => void
  setImageSize: (size: string) => void
  showToast: (msg: string) => void
}

const findPreset = (section: 'chat' | 'image' | 'video', model: string): ModelPreset | undefined => {
  const presets = section === 'chat' ? CHAT_PRESETS : section === 'image' ? IMAGE_PRESETS : VIDEO_PRESETS
  return presets.find(p => p.model === model)
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: makeDefaultSettings(),
  health: 'checking...',
  settingsLoaded: false,
  toast: null,

  initialize: async () => {
    try {
      const s = await window.electronAPI.getSettings()
      if (s && Object.keys(s).length > 0) {
        const merged: AppSettings = { ...makeDefaultSettings(), ...s }
        if (!merged.chat?.apiKey) merged.chat = { ...CHAT_PRESETS[0], ...merged.chat }
        if (!merged.image?.apiKey) merged.image = { ...IMAGE_PRESETS[0], ...merged.image }
        if (!merged.video?.apiKey) merged.video = { ...VIDEO_PRESETS[0], ...merged.video }
        if (!merged.imageSize) merged.imageSize = '16:9'
        if (!merged.sizeMap) merged.sizeMap = { ...DEFAULT_SIZE_MAP }
        set({ settings: merged })
        applyRateLimitDefaults(merged)
      }
    } catch {}
    set({ settingsLoaded: true })
  },

  setHealth: (health: string) => set({ health }),

  showToast: (msg: string) => {
    clearTimeout(toastTimer)
    set({ toast: msg })
    toastTimer = setTimeout(() => set({ toast: null }), 2000)
  },

  updateSetting: (section, field, value) => {
    set(state => ({
      settings: {
        ...state.settings,
        [section]: { ...state.settings[section], [field]: value },
      },
    }))
  },

  onModelChange: (section, model) => {
    const preset = findPreset(section, model)
    if (preset) {
      set(state => ({
        settings: { ...state.settings, [section]: { ...preset } },
      }))
    }
  },

  saveSection: async (section) => {
    const s = get().settings
    try {
      await window.electronAPI.saveSettings(s)
      await fetch(`${BASE}/api/pipeline/rate-limits`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: s[section].model, rpm: parseInt(s[section].rateLimitMin), rpd: parseInt(s[section].rateLimitDay) }),
      })
      get().showToast('保存成功')
    } catch {
      get().showToast('保存失败')
    }
  },

  setSizeTier: (tier: string) => {
    const next = { ...get().settings, sizeTier: tier }
    set({ settings: next })
    window.electronAPI.saveSettings(next).catch(() => {})
  },

  setImageSize: (size: string) => {
    const next = { ...get().settings, imageSize: size }
    set({ settings: next })
    window.electronAPI.saveSettings(next).catch(() => {})
  },
}))

async function applyRateLimitDefaults(s: AppSettings) {
  const defaults: Record<string, [number, number]> = {}
  if (s.chat?.model) defaults[s.chat.model] = [parseInt(s.chat.rateLimitMin) || 50, parseInt(s.chat.rateLimitDay) || 2000]
  if (s.image?.model) defaults[s.image.model] = [parseInt(s.image.rateLimitMin) || 10, parseInt(s.image.rateLimitDay) || 500]
  if (s.video?.model) defaults[s.video.model] = [parseInt(s.video.rateLimitMin) || 50, parseInt(s.video.rateLimitDay) || 1000]
  if (Object.keys(defaults).length === 0) return
  try {
    await fetch(`${BASE}/api/pipeline/rate-limits/defaults`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ defaults }),
    })
  } catch {}
}
