import { useEffect, useState, useRef, useCallback, Fragment } from 'react'
import { getHealth, listProjects, createProject, duplicateProject, checkPipelineRunning, BASE, Project } from './api'
import logoSrc from './logo.jpg'
import Carousel from './Carousel'
import ModelCard from './ModelCard'
import { SIZE_OPTIONS, DEFAULT_SIZE_MAP } from './sizeConfig'

import NewProject from './NewProject'

type Page = 'home' | 'new' | 'settings'

interface NavItem {
  key: string
  icon: string
  label: string
  isPage?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { key: 'home', icon: '⏺', label: '首页', isPage: true },
  { key: 'new', icon: '+', label: '创作', isPage: true },
  { key: 'canvas', icon: '▣', label: '画布' },
  { key: 'asset', icon: '⊞', label: '资产' },
  { key: 'settings', icon: '⚙', label: '设置', isPage: true },
]

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

const CHAT_OPTIONS = CHAT_PRESETS.map(p => p.model)
const IMAGE_OPTIONS = IMAGE_PRESETS.map(p => p.model)
const VIDEO_OPTIONS = VIDEO_PRESETS.map(p => p.model)

const STYLE_LABEL: Record<string, string> = {
  realistic: '写实',
  anime: '动漫',
  cyberpunk: '赛博朋克',
  cinematic: '电影感',
  fantasy: '奇幻',
  minimalist: '极简',
}

const LS_KEY = 'clipsay-ui-state'

interface UiState {
  page: Page
  editProjectId: number | null
}

function loadUiState(): UiState | null {
  try {
    const raw = sessionStorage.getItem(LS_KEY)
    if (!raw) return null
    return JSON.parse(raw) as UiState
  } catch { return null }
}

function saveUiState(state: UiState): void {
  try {
    sessionStorage.setItem(LS_KEY, JSON.stringify(state))
  } catch { /* quota exceeded — ignore */ }
}

function App(): JSX.Element {
  const initState = loadUiState()
  const [page, _setPage] = useState<Page>(initState?.page ?? 'home')
  const [pageRestored, setPageRestored] = useState(false)
  // ── debug: log every page navigation with caller stack ────────
  const setPage = useCallback((p: Page) => {
    console.log(`[nav] page: ${page} -> ${p}`, new Error().stack?.split('\n').slice(2, 5).join(' | '))
    _setPage(p)
  }, [page])
  const [editProjectId, setEditProjectId] = useState<number | undefined>(initState?.editProjectId ?? undefined)
  const [health, setHealth] = useState('checking...')
  const [expanded, setExpanded] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [settings, setSettings] = useState<AppSettings>({
    chat: { ...CHAT_PRESETS[0], rateLimitMin: CHAT_PRESETS[0].rateLimitMin, rateLimitDay: CHAT_PRESETS[0].rateLimitDay },
    image: { ...IMAGE_PRESETS[0], rateLimitMin: IMAGE_PRESETS[0].rateLimitMin, rateLimitDay: IMAGE_PRESETS[0].rateLimitDay },
    video: { ...VIDEO_PRESETS[0], rateLimitMin: VIDEO_PRESETS[0].rateLimitMin, rateLimitDay: VIDEO_PRESETS[0].rateLimitDay },
    imageSize: '16:9',
    sizeMap: { ...DEFAULT_SIZE_MAP }
  })
  const [localSizeMap, setLocalSizeMap] = useState<Record<string, string>>({ ...DEFAULT_SIZE_MAP })
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout>>()

  const showToast = (msg: string) => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 2000)
  }

  const requireNoRunningPipeline = async (): Promise<boolean> => {
    const status = await checkPipelineRunning()
    if (status.running) {
      showToast(`工程 ${status.project_id} 正在创作，请先完成或取消`)
      return false
    }
    return true
  }

  useEffect(() => {
    getHealth().then(r => setHealth(r.status)).catch(() => setHealth('offline'))
    listProjects().then(setProjects).catch(() => {})
    window.electronAPI.getSettings().then(s => {
      if (s && Object.keys(s).length) {
        const merged: AppSettings = { ...s }
        if (!merged.chat?.apiKey) merged.chat = { ...CHAT_PRESETS[0], ...merged.chat }
        if (!merged.image?.apiKey) merged.image = { ...IMAGE_PRESETS[0], ...merged.image }
        if (!merged.video?.apiKey) merged.video = { ...VIDEO_PRESETS[0], ...merged.video }
        if (!merged.imageSize) merged.imageSize = '16:9'
        if (!merged.sizeMap) merged.sizeMap = { ...DEFAULT_SIZE_MAP }
        setSettings(merged)
        applyRateLimitDefaults(merged)
      }
    }).catch(() => {})
    if (initState && initState.page !== 'home') {
      console.log('[nav] restored page from localStorage:', initState.page, 'editProjectId:', initState.editProjectId)
    }
    setPageRestored(true)
  }, [])
  // ── debug: log if page resets to home (possible refresh/crash) ──
  useEffect(() => {
    if (page === 'home') {
      console.log('[nav] mounted/reset to home', new Error().stack?.split('\n').slice(2, 5).join(' | '))
    }
  }, [])

  // ── persist page state to localStorage (sync — survives renderer reload after wake) ──
  useEffect(() => {
    if (!pageRestored) return
    if (page === 'home' && editProjectId === undefined) return
    saveUiState({ page, editProjectId: editProjectId ?? null })
  }, [page, editProjectId, pageRestored])

  // Save on visibilitychange → hidden (sleep/lid-close)
  useEffect(() => {
    const save = () => saveUiState({ page, editProjectId: editProjectId ?? null })
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') save()
    })
    return () => {
      document.removeEventListener('visibilitychange', save)
    }
  }, [page, editProjectId])

  const applyRateLimitDefaults = async (s: AppSettings) => {
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

  useEffect(() => {
    if (settings.sizeMap) {
      setLocalSizeMap({ ...settings.sizeMap })
    }
  }, [page, settings.sizeMap])

  const saveSizeMap = async () => {
    for (const [id, val] of Object.entries(localSizeMap)) {
      if (!/^\d{3,4}x\d{3,4}$/.test(val)) {
        showToast(`保存失败: ${id} 的分辨率格式不正确`)
        return
      }
    }
    const next = { ...settings, sizeMap: { ...localSizeMap } }
    setSettings(next)
    try {
      await window.electronAPI.saveSettings(next)
      showToast('保存成功')
    } catch {
      showToast('保存失败')
    }
  }

  const saveChat = async () => {
    try {
      await window.electronAPI.saveSettings({ ...settings })
      await fetch(`${BASE}/api/pipeline/rate-limits`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: settings.chat.model, rpm: parseInt(settings.chat.rateLimitMin), rpd: parseInt(settings.chat.rateLimitDay) }),
      })
      showToast('保存成功')
    } catch { showToast('保存失败') }
  }
  const saveImage = async () => {
    try {
      await window.electronAPI.saveSettings({ ...settings })
      await fetch(`${BASE}/api/pipeline/rate-limits`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: settings.image.model, rpm: parseInt(settings.image.rateLimitMin), rpd: parseInt(settings.image.rateLimitDay) }),
      })
      showToast('保存成功')
    } catch { showToast('保存失败') }
  }
  const saveVideo = async () => {
    try {
      await window.electronAPI.saveSettings({ ...settings })
      await fetch(`${BASE}/api/pipeline/rate-limits`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: settings.video.model, rpm: parseInt(settings.video.rateLimitMin), rpd: parseInt(settings.video.rateLimitDay) }),
      })
      showToast('保存成功')
    } catch { showToast('保存失败') }
  }

  const onModelChange = (section: 'chat' | 'image' | 'video', model: string) => {
    const presets = section === 'chat' ? CHAT_PRESETS : section === 'image' ? IMAGE_PRESETS : VIDEO_PRESETS
    const preset = presets.find(p => p.model === model)
    if (preset) {
      setSettings(prev => ({
        ...prev,
        [section]: { ...preset }
      }))
    }
  }

  const updateSetting = (section: 'chat' | 'image' | 'video', field: string, value: string) => {
    setSettings(prev => ({ ...prev, [section]: { ...prev[section], [field]: value } }))
  }

  const refreshProjects = () => listProjects().then(setProjects).catch(() => {})

  const handleDuplicate = async (id: number) => {
    if (!await requireNoRunningPipeline()) return
    try {
      const dup = await duplicateProject(id)
      setEditProjectId(dup.id)
      setPage('new')
    } catch {
      showToast('复制失败')
    }
  }

  return (
    <div className="root">
      <div className="titlebar-drag" />
      <div className="app-layout">
      <aside className={`sidebar${expanded ? ' expanded' : ''}`}>
        <div className="sidebar-brand">
          <img className="brand-mark" src={logoSrc} alt="Clipsay" />
          <div className={`brand-info${expanded ? '' : ' collapsed'}`}>
            <span className="brand-label">Clipsay</span>
            <span className="brand-sub">Say it, clip it.</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item, i) => (
            <Fragment key={item.key}>
              {i > 0 && <div className="nav-separator" />}
              <button
                className={`nav-item${item.isPage && page === item.key ? ' active' : ''}`}
                onClick={() => { if (item.isPage) { setEditProjectId(undefined); setPage(item.key as Page) } else showToast('正在开发...') }}
                title={item.label}
              >
                <span className="nav-icon" style={item.key === 'new' ? { fontSize: '1.15rem' } : undefined}>{item.icon}</span>
                <span className={`nav-label${expanded ? '' : ' collapsed'}`}>{item.label}</span>
              </button>
              </Fragment>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`status-dot ${health === 'ok' ? 'online' : 'offline'}`} />
            {expanded && <span className="status-text">{health === 'ok' ? '已连接' : health}</span>}
          </div>
          <button className="sidebar-toggle" onClick={() => setExpanded(!expanded)} title={expanded ? '收起' : '展开'}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points={expanded ? '15 18 9 12 15 6' : '9 18 15 12 9 6'} />
            </svg>
          </button>
        </div>
      </aside>

      <main className="main-content">
        <div className="content">
          {page === 'home' && (
            <>
              <Carousel />
              <div className="hero">
                <h1>欢迎使用 Clipsay</h1>
                <p>用 AI 将你的创意转化为惊艳的视频。</p>
                <button className="btn-primary" onClick={async () => {
                  if (await requireNoRunningPipeline()) {
                    setEditProjectId(undefined); setPage('new')
                  }
                }}>
                  开启创作
                </button>
              </div>

              <div className="section-divider" />
              <h2 className="section-title">创意视频</h2>
              {projects.length === 0 ? (
                <div className="waterfall-empty">暂无创作，点击"开启创作"开始</div>
              ) : (
                <div className="project-grid">
                  {projects.map(p => (
                    <div key={p.id} className="project-card" onClick={async () => {
                      if (await requireNoRunningPipeline()) {
                        setEditProjectId(p.id); setPage('new')
                      }
                    }}>
                      <div className="project-thumb">
                        {(p as any).final_preview ? (
                          <img className="project-thumb-img" src={(p as any).final_preview.startsWith(BASE) ? (p as any).final_preview : `${BASE}${(p as any).final_preview}`} alt="" />
                        ) : (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="project-thumb-icon">
                            <polygon points="5 3 19 12 5 21 5 3" />
                          </svg>
                        )}
                      </div>
                      <div className="project-card-body">
                        <div className="project-name">{p.name || '未命名项目'}</div>
                        <div className="project-actions">
                          <div className="project-meta">{STYLE_LABEL[p.style] || p.style || '写实'}</div>
                          <button className="project-btn" onClick={e => { e.stopPropagation(); setEditProjectId(p.id); setPage('new') }} title="编辑">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                          </button>
                          <button className="project-btn" onClick={e => { e.stopPropagation(); handleDuplicate(p.id) }} title="复制">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {page === 'new' && (
            <NewProject
              onCreated={() => { setEditProjectId(undefined); refreshProjects(); setPage('home') }}
              onCancel={() => { setEditProjectId(undefined); setPage('home') }}
              onProjectSelected={(id) => { setEditProjectId(id) }}
              chatOptions={CHAT_OPTIONS}
              imageOptions={IMAGE_OPTIONS}
              videoOptions={VIDEO_OPTIONS}
              chatApiKey={settings.chat.apiKey}
              chatBaseUrl={settings.chat.baseUrl}
              imageApiKey={settings.image.apiKey}
              imageBaseUrl={settings.image.baseUrl}
              videoApiKey={settings.video.apiKey}
              videoBaseUrl={settings.video.baseUrl}
              chatRateLimitMin={settings.chat.rateLimitMin}
              chatRateLimitDay={settings.chat.rateLimitDay}
              imageRateLimitMin={settings.image.rateLimitMin}
              imageRateLimitDay={settings.image.rateLimitDay}
              videoRateLimitMin={settings.video.rateLimitMin}
              videoRateLimitDay={settings.video.rateLimitDay}
               sizeMap={settings.sizeMap}
               defaultSize={settings.imageSize}
              editProjectId={editProjectId}
            />
          )}

          {page === 'settings' && (
            <div className="settings-page">
              <h2 className="settings-heading">模型</h2>
              <div className="settings-grid">
                <ModelCard
                  title="Chat Model"
                  description="剧本与故事创作"
                  model={settings.chat.model}
                  apiKey={settings.chat.apiKey}
                  baseUrl={settings.chat.baseUrl}
                  rateLimitMin={settings.chat.rateLimitMin}
                  rateLimitDay={settings.chat.rateLimitDay}
                  modelOptions={CHAT_OPTIONS}
                  onModelChange={m => onModelChange('chat', m)}
                  onUpdate={(f, v) => updateSetting('chat', f, v)}
                  onSave={saveChat}
                />
                <ModelCard
                  title="Image Model"
                  description="分镜与肖像设计"
                  model={settings.image.model}
                  apiKey={settings.image.apiKey}
                  baseUrl={settings.image.baseUrl}
                  rateLimitMin={settings.image.rateLimitMin}
                  rateLimitDay={settings.image.rateLimitDay}
                  modelOptions={IMAGE_OPTIONS}
                  onModelChange={m => onModelChange('image', m)}
                  onUpdate={(f, v) => updateSetting('image', f, v)}
                  onSave={saveImage}
                />
                <ModelCard
                  title="Video Model"
                  description="文生与图生视频"
                  model={settings.video.model}
                  apiKey={settings.video.apiKey}
                  baseUrl={settings.video.baseUrl}
                  rateLimitMin={settings.video.rateLimitMin}
                  rateLimitDay={settings.video.rateLimitDay}
                  modelOptions={VIDEO_OPTIONS}
                  onModelChange={m => onModelChange('video', m)}
                  onUpdate={(f, v) => updateSetting('video', f, v)}
                  onSave={saveVideo}
                />
              </div>
              <div className="settings-image">
                <h2 className="settings-heading">图像设置</h2>
                <div className="settings-image-card">
                  <div className="settings-image-header">
                    <span className="settings-card-title">生成尺寸</span>
                  </div>
                  <div className="settings-image-grid">
                    {SIZE_OPTIONS.map(s => (
                      <div key={s.id} className={`settings-image-cell${settings.imageSize === s.id ? ' active' : ''}`} data-aspect={s.id} onClick={() => {
                        const next = { ...settings, imageSize: s.id }
                        setSettings(next)
                        window.electronAPI.saveSettings(next).catch(() => {})
                      }}>
                        <span className="settings-image-cn">{s.labelCn}</span>
                        <div className="settings-image-schema" />
                        <span className="settings-image-label">{s.label}</span>
                        <input
                          className="settings-image-input"
                          value={localSizeMap[s.id] || ''}
                          onChange={e => setLocalSizeMap(prev => ({ ...prev, [s.id]: e.target.value }))}
                        />
                      </div>
                    ))}
                  </div>
                  <div className="settings-image-actions">
                    <button className="btn-primary" onClick={saveSizeMap}>
                      保存
                    </button>
                  </div>
                </div>
              </div>

              <div className="settings-backend">
                <h2 className="settings-heading">后端</h2>
                <div className="settings-backend-card">
                  <div className="settings-backend-row">
                    <span>后端状态</span>
                    <span className={`badge ${health === 'ok' ? 'online' : 'offline'}`}>
                      {health === 'ok' ? '已连接' : '未连接'}
                    </span>
                  </div>
                  <div className="settings-backend-row">
                    <span>端口号</span>
                    <span className="settings-port">8765</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
      {toast && <div className="app-toast">{toast}</div>}
    </div>
    </div>
  )
}

export default App
