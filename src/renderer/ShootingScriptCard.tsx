import { useState, useRef, useCallback, useEffect } from 'react'
import { createPortal } from 'react-dom'
import ImageWithPlaceholder, { type ImageState } from './ImageWithPlaceholder'
import { toCssAspectRatio } from './sizeConfig'
import { useEscClose } from './useEscClose'
import './ShootingScriptCard.css'

export interface ShotData {
  title: string
  visualDescription: string
  voiceDescription: string
  firstFrame: string
  lastFrame: string
  video: string
  videoPreview?: string
  variationType?: string
  firstFramePrompt?: string
  lastFramePrompt?: string
  firstFrameStatus?: ImageState
  lastFrameStatus?: ImageState
  videoStatus?: ImageState
}

export interface ProjectData {
  finalVideo?: string
  finalPreview?: string
}

export interface SceneData {
  title: string
  content: string
  shots: ShotData[]
  compositedVideo: string
  compositedPreview?: string
  compositVideoStatus?: number
}

interface ScriptCardProps {
  scenes: SceneData[]
  loading?: boolean
  creating?: boolean
  disabled?: boolean
  aspectRatio?: string

  onSceneUpdate?: (idx: number, data: SceneData) => void
  onRegenerate?: () => void
  onRefreshFrame?: (sceneIdx: number, shotIdx: number, frameType: 'firstFrame' | 'lastFrame', prompt: string) => void
  onRefreshVideo?: (sceneIdx: number, shotIdx: number) => void
}

export interface MediaPreviewFrame {
  src: string
  isVideo: boolean
  label: string
}

export interface MediaPreviewData {
  items: MediaPreviewFrame[]
  currentIndex: number
}

function buildShotPreviewFrames(shot: ShotData): MediaPreviewFrame[] {
  const items: MediaPreviewFrame[] = []
  if (shot.firstFrame) items.push({ src: shot.firstFrame, isVideo: false, label: '起始帧' })
  if (shot.lastFrame) items.push({ src: shot.lastFrame, isVideo: false, label: '结束帧' })
  if (shot.video) items.push({ src: shot.video, isVideo: true, label: '动态分镜' })
  return items
}

export function MediaPreview({ data, onClose }: { data: MediaPreviewData; onClose: () => void }): JSX.Element {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [index, setIndex] = useState(data.currentIndex)
  const item = data.items[index]

  useEscClose(onClose)

  const navigate = useCallback((dir: -1 | 1) => {
    setIndex(prev => {
      const next = prev + dir
      if (next < 0 || next >= data.items.length) return prev
      return next
    })
  }, [data.items.length])

  useEffect(() => {
    if (item?.isVideo && videoRef.current) {
      videoRef.current.play().catch(() => {})
    }
  }, [index, item])

  useEffect(() => {
    if (!data.items.length) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') navigate(-1)
      else if (e.key === 'ArrowRight') navigate(1)
      else if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, onClose, data.items.length])

  // Lock body scroll when modal is open
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  if (!item) return null

  const modal = (
    <div className="media-preview-backdrop" onClick={onClose}>
      <div className="media-preview-container" onClick={e => e.stopPropagation()}>
        <button className="media-preview-close" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
        {item.isVideo ? (
          <video
            ref={videoRef}
            src={item.src}
            controls
            autoPlay
            className="media-preview-video"
          />
        ) : (
          <img src={item.src} alt={item.label} className="media-preview-image" />
        )}
        {index > 0 && (
          <button className="media-preview-nav media-preview-nav--left" onClick={() => navigate(-1)}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        )}
        {index < data.items.length - 1 && (
          <button className="media-preview-nav media-preview-nav--right" onClick={() => navigate(1)}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
        <div className="media-preview-label">{item.label} ({index + 1}/{data.items.length})</div>
      </div>
    </div>
  )

  return createPortal(modal, document.body)
}

function ShootingScriptCard({ scenes, loading = false, creating = false, disabled = false, aspectRatio = '16:9', onSceneUpdate, onRegenerate, onRefreshFrame, onRefreshVideo }: ScriptCardProps): JSX.Element {
  const cssAspectRatio = toCssAspectRatio(aspectRatio)
  const [editIdx, setEditIdx] = useState<number | null>(null)
  const [editShotKey, setEditShotKey] = useState<{ sceneIdx: number; shotIdx: number } | null>(null)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [mediaPreview, setMediaPreview] = useState<MediaPreviewData | null>(null)

  return (
    <div className="script-card">
      <div className="script-card-header">
        <div className="script-card-title">
          <span className="script-card-title-pill">拍摄脚本</span>
        </div>
        {onRegenerate && (
          <button className="card-refresh-btn" onClick={onRegenerate} title="重新生成">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        )}
      </div>
      {loading && scenes.length === 0 ? (
        <div className="script-card-loading">
          <div className="script-card-loading-icon">✦</div>
          <div className="script-card-loading-text">AI 正在创作</div>
        </div>
      ) : scenes.length === 0 ? (
        <div className="script-card-empty">
          <div className="script-card-empty-text">暂无可用的描述</div>
        </div>
      ) : (
        <div className="script-card-body">
          {scenes.map((scene, idx) => (
            <SceneCard
              key={idx}
              scene={scene}
              sceneIdx={idx}
              sceneKey={`scene-${idx}`}
              hoveredKey={hoveredKey}
              onHover={setHoveredKey}
              onEdit={() => setEditIdx(idx)}
              onEditShot={(shotIdx) => setEditShotKey({ sceneIdx: idx, shotIdx })}
              onRefreshFrame={(shotIdx, frameType, prompt) => onRefreshFrame?.(idx, shotIdx, frameType, prompt)}
              onRefreshVideo={(shotIdx) => onRefreshVideo?.(idx, shotIdx)}
              onRefreshSceneComposited={() => onRefreshVideo?.(idx, -1)}
              onPreview={(items, currentIndex) => setMediaPreview({ items, currentIndex })}
              creating={creating}
              loading={scene.shots.length === 0}
              cssAspectRatio={cssAspectRatio}
            />
          ))}
          
        </div>
      )}

      {editIdx !== null && (
        <SceneEditor
          scene={scenes[editIdx]}
          onSave={(data) => {
            onSceneUpdate?.(editIdx, { ...scenes[editIdx], ...data })
            setEditIdx(null)
          }}
          onClose={() => setEditIdx(null)}
        />
      )}

      {editShotKey !== null && (
        <ShotEditor
          shot={scenes[editShotKey.sceneIdx].shots[editShotKey.shotIdx]}
          cssAspectRatio={cssAspectRatio}
          sceneIdx={editShotKey.sceneIdx}
          shotIdx={editShotKey.shotIdx}
          onSave={(updatedShot) => {
            const scene = scenes[editShotKey.sceneIdx]
            const newShots = [...scene.shots]
            newShots[editShotKey.shotIdx] = updatedShot
            onSceneUpdate?.(editShotKey.sceneIdx, { ...scene, shots: newShots })
          }}
          onRefreshFrame={onRefreshFrame}
          onRefreshVideo={onRefreshVideo}
          onClose={() => setEditShotKey(null)}
          onPreview={(items, currentIndex) => setMediaPreview({ items, currentIndex })}
        />
      )}

      {mediaPreview && (
        <MediaPreview data={mediaPreview} onClose={() => setMediaPreview(null)} />
      )}
    </div>
  )
}

interface SceneCardProps {
  scene: SceneData
  sceneIdx: number
  sceneKey: string
  hoveredKey: string | null
  onHover: (key: string | null) => void
  onEdit: () => void
  onEditShot?: (shotIdx: number) => void
  onRefreshFrame?: (shotIdx: number, frameType: 'firstFrame' | 'lastFrame', prompt: string) => void
  onRefreshVideo?: (shotIdx: number) => void
  onRefreshSceneComposited?: () => void
  onPreview?: (items: MediaPreviewFrame[], clickedIndex: number) => void
  loading?: boolean
  creating?: boolean
  cssAspectRatio?: string
}

function stripScenePrefix(title: string): string {
  return title.replace(/^\s*场景\s*\d+\s*[:：、\-]?\s*/, '').trim()
}

function SceneCard({ scene, sceneIdx, sceneKey, hoveredKey, onHover, onEdit, onEditShot, onRefreshFrame, onRefreshVideo, onRefreshSceneComposited, onPreview, loading = false, creating = false, cssAspectRatio = '16 / 9' }: SceneCardProps): JSX.Element {
  const isHovered = hoveredKey === sceneKey
  const cleanTitle = stripScenePrefix(scene.title) || `场景${sceneIdx + 1}`
  const previewRef = useRef<HTMLDivElement>(null)

  const handlePreviewMouseMove = useCallback((e: React.MouseEvent) => {
    const el = previewRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width * 100).toFixed(1)
    const y = ((e.clientY - rect.top) / rect.height * 100).toFixed(1)
    el.style.setProperty('--glow-x', `${x}%`)
    el.style.setProperty('--glow-y', `${y}%`)
  }, [])

  const handlePreviewMouseLeave = useCallback(() => {
    const el = previewRef.current
    if (!el) return
    el.style.setProperty('--glow-x', '50%')
    el.style.setProperty('--glow-y', '50%')
  }, [])

  return (
    <div
      className={`script-card-item scene-card${isHovered ? ' card-hovered' : ''}`}
      onMouseEnter={() => onHover(sceneKey)}
      onMouseLeave={() => onHover(null)}
    >
      <div className="scene-pill-header">
        <div className="scene-pill">
          <span className="scene-pill-num">场{sceneIdx + 1}</span>
          <span className="scene-pill-title">{cleanTitle}</span>
        </div>
      </div>
      <div className="script-card-item-divider" />

      {loading && creating ? (
        <div className="scene-loading">
          <div className="scene-loading-icon">✦</div>
          <div className="scene-loading-text">正在创作</div>
        </div>
      ) : loading ? (
        <div className="scene-loading">
          <div className="scene-loading-text">暂无可用的描述</div>
        </div>
      ) : (
        <>
      <div className="storyboard-section">
          {scene.shots.map((shot, sidx) => (
            <ShotCard
              key={sidx}
              shot={shot}
              shotIdx={sidx}
              shotKey={`${sceneKey}-shot-${sidx}`}
              hoveredKey={hoveredKey}
              onHover={onHover}
              cssAspectRatio={cssAspectRatio}
              onEdit={() => onEditShot?.(sidx)}
              onRefreshFrame={(frameType, prompt) => onRefreshFrame?.(sidx, frameType, prompt)}
              onRefreshVideo={() => onRefreshVideo?.(sidx)}
              onPreview={onPreview}
            />
          ))}
      </div>

      <div className="script-card-item-divider" />

      <div className="scene-preview-card" ref={previewRef} onMouseMove={handlePreviewMouseMove} onMouseLeave={handlePreviewMouseLeave} style={{ cursor: 'default' }}>
        <span className="scene-preview-card-pill">场景预览</span>
        {onRefreshSceneComposited && (
          <button className="scene-preview-refresh-btn" onClick={(e) => { e.stopPropagation(); onRefreshSceneComposited() }} title="重新生成场景预览">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        )}
        <div className="shot-card-body">
          <div className="scene-composited-video">
            {scene.compositedVideo ? (
              <FrameCard
                label=""
                src={scene.compositedVideo}
                previewSrc={scene.compositedPreview}
                frameKey={`${sceneKey}-composited`}
                hoveredKey={hoveredKey}
                onHover={onHover}
                isVideo
                frameStyle={{ aspectRatio: cssAspectRatio, width: '100%', height: 'auto' }}
                onClick={() => onPreview?.([{ src: scene.compositedVideo!, isVideo: true, label: '场景预览' }], 0)}
              />
            ) : (
              <ImageWithPlaceholder
                src=""
                alt="场景预览"
                status={
                  scene.compositVideoStatus === 1
                    ? 'generating'
                    : scene.compositVideoStatus === 2
                      ? 'generated'
                      : scene.compositVideoStatus === 3
                        ? 'error'
                        : 'waiting'
                }
                style={{ aspectRatio: cssAspectRatio, width: '100%', borderRadius: '6px', objectFit: 'cover' }}
              />
            )}
          </div>
        </div>
      </div>
        </>
      )}
    </div>
  )
}

interface ShotCardProps {
  shot: ShotData
  shotIdx: number
  shotKey: string
  hoveredKey: string | null
  onHover: (key: string | null) => void
  cssAspectRatio?: string
  onEdit?: () => void
  onRefreshFrame?: (frameType: 'firstFrame' | 'lastFrame', prompt: string) => void
  onRefreshVideo?: () => void
  onPreview?: (items: MediaPreviewFrame[], clickedIndex: number) => void
}

function stripShotPrefix(title?: string): string {
  if (!title) return ''
  return title.replace(/^\s*镜\s*头?\s*\d+\s*[:：、\-]?\s*/, '').trim()
}

function ShotCard({ shot, shotIdx, shotKey, hoveredKey, onHover, cssAspectRatio = '16 / 9', onEdit, onRefreshFrame, onRefreshVideo, onPreview }: ShotCardProps): JSX.Element {
  const isHovered = hoveredKey === shotKey
  const cleanTitle = stripShotPrefix(shot.title) || `镜头${shotIdx + 1}`
  const shotRef = useRef<HTMLDivElement>(null)

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const el = shotRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width * 100).toFixed(1)
    const y = ((e.clientY - rect.top) / rect.height * 100).toFixed(1)
    el.style.setProperty('--glow-x', `${x}%`)
    el.style.setProperty('--glow-y', `${y}%`)
  }, [])

  const handleMouseLeaveCard = useCallback(() => {
    const el = shotRef.current
    if (!el) return
    el.style.setProperty('--glow-x', '50%')
    el.style.setProperty('--glow-y', '50%')
  }, [])

  const handleFramePreview = useCallback((clickedSrc: string) => {
    const items = buildShotPreviewFrames(shot)
    const idx = items.findIndex(i => i.src === clickedSrc)
    if (idx >= 0) onPreview?.(items, idx)
  }, [shot, onPreview])
  return (
    <div
      ref={shotRef}
      className={`shot-card${isHovered ? ' card-hovered' : ''}`}
      onMouseEnter={() => onHover(shotKey)}
      onMouseMove={handleMouseMove}
      onMouseLeave={(e) => { onHover(null); handleMouseLeaveCard(e) }}
    >
      <div className="shot-pill-header">
        <div className="shot-pill">
          <span className="shot-pill-num">镜头{shotIdx + 1}</span>
        </div>
        <button className="script-card-edit-btn shot-edit-btn" onClick={onEdit} title="编辑">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </button>
      </div>
      <div className="shot-card-body">
        <div className="shot-card-desc">
          <div className="shot-card-row">
            <span className="shot-card-tag">[视觉描述]</span>
            <span className="shot-card-text">{shot.visualDescription}</span>
          </div>
          <div className="shot-card-row">
            <span className="shot-card-tag">[对白音效]</span>
            <span className="shot-card-text">{shot.voiceDescription}</span>
          </div>
        </div>
        <div className="shot-card-frames">
          <FrameCard
            label="起始帧"
            src={shot.firstFrame}
            frameKey={`${shotKey}-frame-0`}
            hoveredKey={hoveredKey}
            onHover={onHover}
            className="order-1"
            frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
            onRefresh={shot.firstFrame ? () => onRefreshFrame?.('firstFrame', shot.firstFramePrompt || '') : undefined}
            onClick={() => handleFramePreview(shot.firstFrame)}
            status={shot.firstFrameStatus}
          />
          <FrameCard
            label="结束帧"
            src={shot.lastFrame}
            frameKey={`${shotKey}-frame-1`}
            hoveredKey={hoveredKey}
            onHover={onHover}
            className="order-2"
            frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
            onRefresh={shot.lastFrame ? () => onRefreshFrame?.('lastFrame', shot.lastFramePrompt || '') : undefined}
            onClick={() => handleFramePreview(shot.lastFrame)}
            status={shot.lastFrameStatus}
          />
          <FrameCard
            label="动态分镜"
            src={shot.video}
            previewSrc={shot.videoPreview}
            frameKey={`${shotKey}-video`}
            hoveredKey={hoveredKey}
            onHover={onHover}
            isVideo
            className="order-3"
            frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
            onRefresh={shot.video ? onRefreshVideo : undefined}
            onClick={() => handleFramePreview(shot.video)}
            status={shot.videoStatus}
          />
        </div>

      </div>
    </div>
  )
}

interface FrameCardProps {
  label: string
  src: string
  frameKey: string
  hoveredKey: string | null
  onHover: (key: string | null) => void
  isVideo?: boolean
  previewSrc?: string
  className?: string
  hideWhenPlaceholder?: boolean
  frameStyle?: React.CSSProperties
  onRefresh?: () => void
  onClick?: () => void
  status?: ImageState
}

export function isDataUri(url: string): boolean {
  return !url || url.startsWith('data:')
}

export function FrameCard({ label, src, frameKey, hoveredKey, onHover, isVideo, previewSrc, className, hideWhenPlaceholder, frameStyle, onRefresh, onClick, status }: FrameCardProps): JSX.Element {
  const isHovered = hoveredKey === frameKey
  const isPlaceholder = isDataUri(src)
  const hideLast = hideWhenPlaceholder && !isVideo && isPlaceholder && label === '尾帧'
  const [localRefreshState, setLocalRefreshState] = useState<'idle' | 'generating'>('idle')
  const prevSrcRef = useRef(src)

  if (hideLast) return <div className={`shot-card-frame${className ? ' ' + className : ''}`} />

  const handleClick = () => {
    if (onClick && !isPlaceholder) {
      onClick()
    }
  }

  const handleRefresh = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (!onRefresh) return
    prevSrcRef.current = src
    setLocalRefreshState('generating')
    onRefresh()
  }, [onRefresh, src])

  // Reset local refresh state when src changes (new image arrived)
  useEffect(() => {
    if (localRefreshState === 'generating' && src !== prevSrcRef.current) {
      prevSrcRef.current = src
      setLocalRefreshState('idle')
    }
  }, [src, localRefreshState])

  // Safety timeout: force-reset after 60s if stuck
  useEffect(() => {
    if (localRefreshState !== 'generating') return
    const timer = setTimeout(() => setLocalRefreshState('idle'), 60000)
    return () => clearTimeout(timer)
  }, [localRefreshState])

  const effectiveStatus = localRefreshState === 'generating' ? 'generating' : status

  return (
    <div
      className={`shot-card-frame${isHovered ? ' card-hovered' : ''}${className ? ' ' + className : ''}`}
      onMouseEnter={() => onHover(frameKey)}
      onMouseLeave={() => onHover(null)}
      onClick={handleClick}
    >
      {label && <span className="shot-card-image-label">{label}</span>}
      <div className="shot-card-media-wrap">
        {isVideo ? (
          isPlaceholder ? (
            <ImageWithPlaceholder
              key={src}
              src={src}
              alt={label}
              status={effectiveStatus || 'waiting'}
              className="shot-card-img"
              style={frameStyle}
            />
          ) : (
            <div key={src} className="shot-card-video-placeholder" style={{ backgroundImage: `url(${previewSrc || src})`, ...frameStyle }}>
              <svg className="shot-card-play-icon" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
              <video src={src} muted preload="metadata" style={{ display: 'none' }} />
            </div>
          )
        ) : (
          <ImageWithPlaceholder
            key={src}
            src={src}
            alt={label}
            status={effectiveStatus || (isPlaceholder ? 'waiting' : 'generated')}
            className="shot-card-img"
            style={frameStyle}
          />
        )}
        {onRefresh && (
          <button className="frame-refresh-btn" onClick={handleRefresh} title="重新生成">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}

interface SceneEditorProps {
  scene: SceneData
  onSave: (data: { title: string; content: string }) => void
  onClose: () => void
}

function SceneEditor({ scene, onSave, onClose }: SceneEditorProps): JSX.Element {
  const [title, setTitle] = useState(scene.title)
  const [content, setContent] = useState(scene.content)
  const savedRef = useRef({ title: scene.title, content: scene.content })
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout>>()
  useEscClose(onClose)

  const dirty = title !== savedRef.current.title || content !== savedRef.current.content

  const showToast = (msg: string) => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 2000)
  }

  const handleSave = () => {
    savedRef.current = { title, content }
    onSave({ title, content })
    showToast('保存成功')
  }

  return (
    <div className="story-editor-backdrop" onClick={onClose}>
      <div className="scene-editor-dialog" onClick={e => e.stopPropagation()}>
        <div className="story-editor-header">
          <div className="story-editor-title">编辑 — {scene.title}</div>
          <div className="story-editor-actions">
            <button
              className={`story-editor-btn${!dirty ? ' story-editor-btn-disabled' : ''}`}
              onClick={handleSave}
              disabled={!dirty}
              title="保存"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                <polyline points="17 21 17 13 7 13 7 21" />
                <polyline points="7 3 7 8 15 8" />
              </svg>
            </button>
            <button className="story-editor-btn" onClick={onClose} title="关闭">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
        <div className="story-editor-divider" />

        <div className="scene-editor-body">
          <div className="scene-editor-row">
            <div className="scene-editor-row-label">标题</div>
            <input className="scene-editor-input" value={title} onChange={e => setTitle(e.target.value)} />
          </div>
          <div className="scene-editor-row" style={{ marginTop: '10px' }}>
            <div className="scene-editor-row-label">内容</div>
            <textarea className="scene-editor-textarea" value={content} onChange={e => setContent(e.target.value)} />
          </div>
        </div>
      </div>
      {toast && <div className="story-editor-toast">{toast}</div>}
    </div>
  )
}

interface ShotEditorProps {
  shot: ShotData
  cssAspectRatio: string
  sceneIdx: number
  shotIdx: number
  onSave?: (shot: ShotData) => void
  onRefreshFrame?: (sceneIdx: number, shotIdx: number, frameType: 'firstFrame' | 'lastFrame', prompt: string) => void
  onRefreshVideo?: (sceneIdx: number, shotIdx: number) => void
  onClose: () => void
  onPreview?: (items: MediaPreviewFrame[], clickedIndex: number) => void
}

function ShotEditor({ shot, cssAspectRatio, sceneIdx, shotIdx, onSave, onRefreshFrame, onRefreshVideo, onClose, onPreview }: ShotEditorProps): JSX.Element {
  const [visualDesc, setVisualDesc] = useState(shot.visualDescription)
  const [voiceDesc, setVoiceDesc] = useState(shot.voiceDescription)
  const taRefs = useRef<(HTMLTextAreaElement | null)[]>([])
  const autoResize = (el: HTMLTextAreaElement | null) => {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = el.scrollHeight + 'px'
  }
  useEffect(() => { taRefs.current.forEach(autoResize) }, [visualDesc, voiceDesc])
  const handleFramePreview = useCallback((clickedSrc: string) => {
    const items = buildShotPreviewFrames(shot)
    const idx = items.findIndex(i => i.src === clickedSrc)
    if (idx >= 0) onPreview?.(items, idx)
  }, [shot, onPreview])
  const cleanTitle = stripShotPrefix(shot.title) || `镜头${shotIdx + 1}`
  useEscClose(onClose)

  const dirty = visualDesc !== shot.visualDescription || voiceDesc !== shot.voiceDescription

  const handleSave = () => {
    if (!dirty) return
    onSave?.({ ...shot, visualDescription: visualDesc, voiceDescription: voiceDesc })
    onClose()
  }

  return (
    <div className="story-editor-backdrop" onClick={onClose}>
      <div className="shot-editor-dialog" onClick={e => e.stopPropagation()}>
        <div className="story-editor-header">
          <div className="story-editor-title">编辑 - 镜头{shotIdx + 1}</div>
          <div className="story-editor-actions">
            <button
              className={`story-editor-btn story-editor-btn-save${!dirty ? ' story-editor-btn-disabled' : ''}`}
              onClick={handleSave}
              disabled={!dirty}
              title="保存 (⌘Enter)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>保存</span>
            </button>
            <button className="story-editor-btn" onClick={onClose} title="关闭 (Esc)">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
        <div className="shot-editor-body">
          <div className="shot-editor-row">
            <div className="shot-editor-row-label">视觉描述</div>
            <textarea className="shot-editor-textarea shot-editor-textarea--visual" ref={el => { taRefs.current[0] = el; autoResize(el) }} value={visualDesc} onChange={e => setVisualDesc(e.target.value)} />
          </div>
          <div className="shot-editor-row">
            <div className="shot-editor-row-label">对白音效</div>
            <textarea className="shot-editor-textarea shot-editor-textarea--voice" ref={el => { taRefs.current[1] = el; autoResize(el) }} value={voiceDesc} onChange={e => setVoiceDesc(e.target.value)} />
          </div>
          <div className="shot-editor-row">
            <div className="shot-editor-row-label">分镜帧</div>
            <div className="shot-editor-frames-wrap">
              <div className="shot-editor-frames">
                <FrameCard
                  label="起始帧"
                  src={shot.firstFrame}
                  frameKey={`edit-shot-${sceneIdx}-${shotIdx}-frame-0`}
                  hoveredKey={null}
                  onHover={() => {}}
                  frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
                  onRefresh={shot.firstFrame ? () => onRefreshFrame?.(sceneIdx, shotIdx, 'firstFrame', shot.firstFramePrompt || '') : undefined}
                  onClick={() => handleFramePreview(shot.firstFrame)}
                  status={shot.firstFrameStatus}
                />
                <FrameCard
                  label="结束帧"
                  src={shot.lastFrame}
                  frameKey={`edit-shot-${sceneIdx}-${shotIdx}-frame-1`}
                  hoveredKey={null}
                  onHover={() => {}}
                  frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
                  onRefresh={shot.lastFrame ? () => onRefreshFrame?.(sceneIdx, shotIdx, 'lastFrame', shot.lastFramePrompt || '') : undefined}
                  onClick={() => handleFramePreview(shot.lastFrame)}
                  status={shot.lastFrameStatus}
                />
                <FrameCard
                  label="动态分镜"
                  src={shot.video}
                  previewSrc={shot.videoPreview}
                  frameKey={`edit-shot-${sceneIdx}-${shotIdx}-video`}
                  hoveredKey={null}
                  onHover={() => {}}
                  isVideo
                  frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
                  onRefresh={shot.video ? () => onRefreshVideo?.(sceneIdx, shotIdx) : undefined}
                  onClick={() => handleFramePreview(shot.video)}
                  status={shot.videoStatus}
                />
              </div>
            </div>
          </div>
        </div>
        <div className="story-editor-footer">
          <span className="story-editor-hint">⌘Enter 保存 · Esc 关闭</span>
        </div>
      </div>
    </div>
  )
}

export default ShootingScriptCard
