import { useEffect, useState, useRef, useCallback, Fragment, type ReactNode } from 'react'
import { getHealth, listProjects, createProject, duplicateProject, checkPipelineRunning, listTopCompletedProjects, incrementProjectClick, BASE, Project } from './api'
import logoSrc from './logo.jpg'
import Carousel, { CarouselSlide } from './Carousel'
import ProjectCard from './ProjectCard'
import ModelCard from './ModelCard'
import { SIZE_OPTIONS, DEFAULT_SIZE_MAP } from './sizeConfig'

const SIZE_TIERS = [
  { id: '1K', label: 'Basic', subLabel: '1K' },
  { id: '2K', label: 'HD', subLabel: '2K' },
  { id: '3K', label: 'Ultra HD', subLabel: '3K' },
  { id: '4K', label: '4K UHD', subLabel: '4K' },
]

import NewProject from './NewProject'

type Page = 'home' | 'new' | 'settings'

const HomeIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="nav-svg">
    <path d="M3 10L12 3l9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10z" />
    <path d="M9 21V13h6v8" />
  </svg>
)

const PlusIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="nav-svg">
    <circle cx="12" cy="12" r="8.5" />
    <path d="M8 12h8" />
    <path d="M12 8v8" />
  </svg>
)

const GridIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="nav-svg">
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
  </svg>
)

const FolderIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="nav-svg">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    <path d="M3 10h18" />
  </svg>
)

const SettingsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="nav-svg">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
)

interface NavItem {
  key: string
  icon: ReactNode
  label: string
  isPage?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { key: 'home', icon: <HomeIcon />, label: '首页', isPage: true },
  { key: 'new', icon: <PlusIcon />, label: '创作', isPage: true },
  { key: 'canvas', icon: <GridIcon />, label: '画布' },
  { key: 'asset', icon: <FolderIcon />, label: '资产' },
  { key: 'settings', icon: <SettingsIcon />, label: '设置', isPage: true },
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
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  // ── debug: log every page navigation with caller stack ────────
  const setPage = useCallback((p: Page) => {
    console.log(`[nav] page: ${page} -> ${p}`, new Error().stack?.split('\n').slice(2, 5).join(' | '))
    _setPage(p)
  }, [page])
  const [editProjectId, setEditProjectId] = useState<number | undefined>(initState?.editProjectId ?? undefined)
  const [health, setHealth] = useState('checking...')
  const [expanded, setExpanded] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [topProjects, setTopProjects] = useState<Project[]>([])
  const [settings, setSettings] = useState<AppSettings>({
    chat: { ...CHAT_PRESETS[0], rateLimitMin: CHAT_PRESETS[0].rateLimitMin, rateLimitDay: CHAT_PRESETS[0].rateLimitDay },
    image: { ...IMAGE_PRESETS[0], rateLimitMin: IMAGE_PRESETS[0].rateLimitMin, rateLimitDay: IMAGE_PRESETS[0].rateLimitDay },
    video: { ...VIDEO_PRESETS[0], rateLimitMin: VIDEO_PRESETS[0].rateLimitMin, rateLimitDay: VIDEO_PRESETS[0].rateLimitDay },
    imageSize: '16:9',
    sizeTier: '1K',
    sizeMap: { ...DEFAULT_SIZE_MAP }
  })
  const [toast, setToast] = useState<string | null>(null)
  const [playVideoUrl, setPlayVideoUrl] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout>>()

  const showToast = (msg: string) => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 2000)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setPlayVideoUrl(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

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
    listTopCompletedProjects().then(setTopProjects).catch(() => {})
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
      setSettingsLoaded(true)
    }).catch(() => { setSettingsLoaded(true) })
    if (initState && initState.page !== 'home') {
      console.log('[nav] restored page from localStorage:', initState.page, 'editProjectId:', initState.editProjectId)
    }
    setPageRestored(true)
  }, [])
  // ── debug: log if page resets to home on mount (after state restoration) ──
  useEffect(() => {
    if (page === 'home' && !initState?.page) {
      console.log('[nav] mounted to home (no saved state)', new Error().stack?.split('\n').slice(2, 5).join(' | '))
    }
  }, [page, initState])

  // ── listen for window maximize → collapse sidebar ──
  useEffect(() => {
    window.electronAPI?.onWindowState?.(({ isMaximized }) => {
      if (isMaximized) setExpanded(false)
      document.body.classList.toggle('window-maximized', isMaximized)
      if (!isMaximized) document.body.classList.remove('show-new-sidebar')
    })
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

  const refreshProjects = () => {
    listProjects().then(setProjects).catch(() => {})
    listTopCompletedProjects().then(setTopProjects).catch(() => {})
  }

  const buildCarouselSlides = (projects: Project[]): CarouselSlide[] => {
    const DEFAULT_SLIDES: CarouselSlide[] = [
      { type: 'default', title: 'Seedance 2.0', storyTitle: 'Seedance 2.0', desc: 'AI 视频生成，前所未有的画质与一致性' },
      { type: 'default', title: '创作者挑战赛', storyTitle: '创作者挑战赛', desc: '参与挑战，赢取大奖与曝光机会' },
      { type: 'default', title: '智能剪辑', storyTitle: '智能剪辑', desc: 'AI 自动识别高光片段，一键成片' },
      { type: 'default', title: '语音转字幕', storyTitle: '语音转字幕', desc: '精准语音识别，自动生成多语言字幕' },
    ]
    const projectSlides: CarouselSlide[] = projects.map(p => ({
      type: 'project' as const,
      projectId: p.id,
      title: p.name,
      storyTitle: (p as any).story_title || p.name,
      desc: p.idea,
      previewUrl: p.final_preview ? (p.final_preview.startsWith(BASE) ? p.final_preview : `${BASE}${p.final_preview}`) : undefined,
      videoUrl: p.final_video ? (p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}`) : undefined,
    }))
    if (projectSlides.length >= 4) return projectSlides.slice(0, 4)
    return [...projectSlides, ...DEFAULT_SLIDES.slice(0, 4 - projectSlides.length)]
  }

  const handleCarouselSlideClick = async (projectId: number) => {
    if (await requireNoRunningPipeline()) {
      incrementProjectClick(projectId).catch(() => {})
      setEditProjectId(projectId); setPage('new')
    }
  }

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
      <aside className={`sidebar${expanded ? ' expanded' : ''}`} onDoubleClick={() => document.body.classList.toggle('show-new-sidebar')}>
        <div className="sidebar-brand">
          <img className="brand-mark" src={logoSrc} alt="Clipsay" />
          <div className={`brand-info${expanded ? '' : ' collapsed'}`}>
            <span className="brand-label">Clipsay</span>
            <span className="brand-sub">Say it, clip it </span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item, i) => (
            <Fragment key={item.key}>
              {i > 0 && <div className="nav-separator" />}
              <button
                className={`nav-item${item.isPage && page === item.key ? ' active' : ''}`}
                onClick={() => { if (item.isPage) { 
                  if (item.key === 'home') refreshProjects()
                  setEditProjectId(undefined); setPage(item.key as Page) 
                } else showToast('正在开发...') }}
                title={item.label}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className={`nav-label${expanded ? '' : ' collapsed'}`}>{item.label}</span>
              </button>
              </Fragment>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`status-dot ${health === 'ok' ? 'online' : 'offline'}`} />
            <span className={`status-text${expanded ? '' : ' collapsed'}`}>{health === 'ok' ? '已连接' : health}</span>
          </div>
          <button className="sidebar-toggle" onClick={() => setExpanded(!expanded)} title={expanded ? '收起' : '展开'}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.5s cubic-bezier(0.32,0.72,0,1)' }}>
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
        <div className="sidebar-hint" title="双击展开创作面板">⠇</div>
      </aside>

      <main className="main-content">
        <div className="content">
          {page === 'home' && (
            <>
              <Carousel slides={buildCarouselSlides(topProjects)} onSlideClick={handleCarouselSlideClick} />

              <div className="home-welcome">
                <div className="home-welcome-text">
                  <h1>转化为惊艳的视频</h1>
                  <p>输入想法，AI 一键生成专业视频</p>
                  <button className="btn-primary" onClick={async () => {
                    if (await requireNoRunningPipeline()) {
                      setEditProjectId(undefined); setPage('new')
                    }
                  }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3" /></svg>
                    开启创作
                  </button>
                </div>
                <div className="home-welcome-stats">
                  <div className="home-stat">
                    <span className="home-stat-value">{projects.length}</span>
                    <span className="home-stat-label">作品</span>
                  </div>
                  <div className="home-stat">
                    <span className="home-stat-value">4</span>
                    <span className="home-stat-label">AI 模型</span>
                  </div>
                  <div className="home-stat">
                    <span className="home-stat-value">{topProjects.length > 0 ? topProjects.length : '∞'}</span>
                    <span className="home-stat-label">精选</span>
                  </div>
                </div>
              </div>

              <div className="home-section">
                <div className="home-section-head">
                  <h2>全部作品</h2>
                </div>
                {projects.length === 0 ? (
                  <div className="home-empty">
                    <div className="home-empty-icon">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="16" /><line x1="8" y1="12" x2="16" y2="12" /></svg>
                    </div>
                    <p>还没有作品，开始你的第一个创作</p>
                    <button className="btn-secondary" onClick={async () => {
                      if (await requireNoRunningPipeline()) {
                        setEditProjectId(undefined); setPage('new')
                      }
                    }}>开启创作</button>
                  </div>
                ) : (
                  <div className="project-grid">
                    {projects.map((p, i) => (
                      <ProjectCard
                        key={p.id}
                        project={p}
                        index={i}
                        onPlay={(url) => setPlayVideoUrl(url)}
                        onEdit={(id) => { setEditProjectId(id); setPage('new') }}
                        onDuplicate={handleDuplicate}
                        onOpen={(id) => { setEditProjectId(id); setPage('new') }}
                        onIncrementClick={(id) => incrementProjectClick(id).catch(() => {})}
                      />
                    ))}
                  </div>
                )}
              </div>
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
               defaultSizeTier={settings.sizeTier}
              editProjectId={editProjectId}
            />
          )}

          {page === 'settings' && settingsLoaded && (
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
                <div className="settings-image-cards-row">
                  <div className="settings-image-card-outer">
                    <div className="settings-image-card">
                      <div className="settings-image-header">
                        <span className="settings-card-title">尺寸</span>
                      </div>
                      <div className="settings-image-grid">
                        {SIZE_TIERS.map(t => (
                          <div
                            key={t.id}
                            className={`settings-image-cell${settings.sizeTier === t.id ? ' active' : ''}`}
                            onClick={() => {
                              const next = { ...settings, sizeTier: t.id }
                              setSettings(next)
                              window.electronAPI.saveSettings(next).catch(() => {})
                            }}
                          >
                            <span className="settings-image-label">{t.label}</span>
                            <span className="settings-image-sub">{t.subLabel}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="settings-image-card-outer">
                    <div className="settings-image-card">
                      <div className="settings-image-header">
                        <span className="settings-card-title">宽高比</span>
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
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="settings-backend">
                <h2 className="settings-heading">后端</h2>
                <div className="settings-backend-card-outer">
                  <div className="settings-backend-card">
                    <div className="settings-backend-row">
                      <span className="settings-backend-label">后端状态</span>
                      <span className="settings-backend-value">
                        <span className={`badge ${health === 'ok' ? 'online' : 'offline'}`}>
                          <span className="badge-dot" />
                          {health === 'ok' ? '已连接' : '未连接'}
                        </span>
                      </span>
                    </div>
                    <div className="settings-backend-row">
                      <span className="settings-backend-label">端口号</span>
                      <span className="settings-backend-value">
                        <span className="settings-port">8765</span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
      {playVideoUrl && (
        <div className="carousel-modal-overlay" onClick={() => setPlayVideoUrl(null)}>
          <div className="carousel-modal" onClick={e => e.stopPropagation()}>
            <video key={playVideoUrl} className="carousel-modal-video" src={playVideoUrl} autoPlay loop playsInline controls />
            <button className="carousel-modal-close" onClick={() => setPlayVideoUrl(null)}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>
        </div>
      )}
      {toast && <div className="app-toast">{toast}</div>}
    </div>
    </div>
  )
}

export default App
