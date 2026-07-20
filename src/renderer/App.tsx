import { useEffect, useState, useCallback, Fragment, type ReactNode, useMemo } from 'react'
import { getHealth, BASE, type Project } from './api'
import logoSrc from './logo.jpg'
import Carousel from './Carousel'
import ProjectCard from './ProjectCard'
import ModelCard from './ModelCard'
import { SIZE_OPTIONS } from './sizeConfig'
import { useSettingsStore, CHAT_OPTIONS, IMAGE_OPTIONS, VIDEO_OPTIONS } from './stores/settingsStore'
import { useProjectStore, buildCarouselSlides, requireNoRunningPipeline } from './stores/projectStore'

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
  const [expanded, setExpanded] = useState(false)

  const toast = useSettingsStore(s => s.toast)
  const showToast = useSettingsStore(s => s.showToast)
  const health = useSettingsStore(s => s.health)
  const settings = useSettingsStore(s => s.settings)
  const settingsLoaded = useSettingsStore(s => s.settingsLoaded)
  const setSizeTier = useSettingsStore(s => s.setSizeTier)
  const setImageSize = useSettingsStore(s => s.setImageSize)
  const projects = useProjectStore(s => s.projects)
  const topProjects = useProjectStore(s => s.topProjects)
  const playVideo = useProjectStore(s => s.playVideo)
  const setPlayVideo = useProjectStore(s => s.setPlayVideo)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') useProjectStore.getState().setPlayVideo(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    useSettingsStore.getState().initialize()
    getHealth().then(r => useSettingsStore.getState().setHealth(r.status)).catch(() => useSettingsStore.getState().setHealth('offline'))
    useProjectStore.getState().refreshProjects()
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

  return (
    <div className="root">
      <div className="titlebar-drag" />
      <div className="app-layout">
      <aside className={`sidebar${expanded ? ' expanded' : ''}`} onDoubleClick={() => { if (page === 'new') document.body.classList.toggle('show-new-sidebar') }}>
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
                  if (item.key === 'home') useProjectStore.getState().refreshProjects()
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
              <Carousel slides={useMemo(() => buildCarouselSlides(topProjects), [topProjects])} onSlideClick={async (projectId) => { if (await requireNoRunningPipeline()) { useProjectStore.getState().incrementClick(projectId); setEditProjectId(projectId); setPage('new') } }} />

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
                        projectId={p.id}
                        index={i}
                        onEdit={(id) => { setEditProjectId(id); setPage('new') }}
                        onOpen={(id) => { setEditProjectId(id); setPage('new') }}
                      />
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {page === 'new' && (
            <NewProject
              onCreated={() => { setEditProjectId(undefined); useProjectStore.getState().refreshProjects(); setPage('home') }}
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
                <ModelCard section="chat" title="Chat Model" description="剧本与故事创作" modelOptions={CHAT_OPTIONS} />
                <ModelCard section="image" title="Image Model" description="分镜与肖像设计" modelOptions={IMAGE_OPTIONS} />
                <ModelCard section="video" title="Video Model" description="文生与图生视频" modelOptions={VIDEO_OPTIONS} />
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
                            onClick={() => setSizeTier(t.id)}
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
                          <div key={s.id} className={`settings-image-cell${settings.imageSize === s.id ? ' active' : ''}`} data-aspect={s.id} onClick={() => setImageSize(s.id)}>
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
      {playVideo && (
        <div className="carousel-modal-overlay" onClick={() => setPlayVideo(null)}>
          <div className="carousel-modal" onClick={e => e.stopPropagation()}>
            <button className="carousel-modal-close" onClick={() => setPlayVideo(null)}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
            <video key={playVideo.url} className="carousel-modal-video" src={playVideo.url} autoPlay loop playsInline controls />
            <div className="carousel-modal-top">
              <span className="carousel-modal-title">{playVideo.title}</span>
            </div>
          </div>
        </div>
      )}
      {toast && <div className="app-toast">{toast}</div>}
    </div>
    </div>
  )
}

export default App
