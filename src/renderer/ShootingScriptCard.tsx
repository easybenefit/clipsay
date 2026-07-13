import { useState, useRef, useCallback, useEffect } from 'react'
import ImageWithPlaceholder, { type ImageState } from './ImageWithPlaceholder'
import { toCssAspectRatio } from './sizeConfig'
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
}

interface ScriptCardProps {
  scenes: SceneData[]
  loading?: boolean
  disabled?: boolean
  aspectRatio?: string

  onSceneUpdate?: (idx: number, data: SceneData) => void
  onRegenerate?: () => void
  onRefreshFrame?: (sceneIdx: number, shotIdx: number, frameType: 'firstFrame' | 'lastFrame', prompt: string) => void
}

export interface MediaPreviewData {
  src: string
  isVideo: boolean
  label: string
}

export function MediaPreview({ data, onClose }: { data: MediaPreviewData; onClose: () => void }): JSX.Element {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (data.isVideo && videoRef.current) {
      videoRef.current.play().catch(() => {})
    }
  }, [data])

  return (
    <div className="media-preview-backdrop" onClick={onClose}>
      <div className="media-preview-container" onClick={e => e.stopPropagation()}>
        <button className="media-preview-close" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
        {data.isVideo ? (
          <video
            ref={videoRef}
            src={data.src}
            controls
            autoPlay
            muted
            className="media-preview-video"
          />
        ) : (
          <img src={data.src} alt={data.label} className="media-preview-image" />
        )}
        <div className="media-preview-label">{data.label}</div>
      </div>
    </div>
  )
}

function ShootingScriptCard({ scenes, loading = false, disabled = false, aspectRatio = '16:9', onSceneUpdate, onRegenerate, onRefreshFrame }: ScriptCardProps): JSX.Element {
  const cssAspectRatio = toCssAspectRatio(aspectRatio)
  const [editIdx, setEditIdx] = useState<number | null>(null)
  const [editShotKey, setEditShotKey] = useState<{ sceneIdx: number; shotIdx: number } | null>(null)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [mediaPreview, setMediaPreview] = useState<MediaPreviewData | null>(null)

  return (
    <div className="script-card">
      <div className="script-card-header">
        <div className="script-card-title">拍摄脚本</div>
        {!loading && scenes.length > 0 && (
          <div className="script-card-actions">
            <button className={`story-link${disabled ? ' story-link-disabled' : ''}`} title="重新创作" onClick={() => !disabled && onRegenerate?.()}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            </button>
            <span className="story-link-sep">|</span>
            <button className="story-link story-link-disabled" title="编辑" disabled>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="script-card-divider" />
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
              onPreview={(src, isVideo, label) => setMediaPreview({ src, isVideo, label })}
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
          onRefreshFrame={onRefreshFrame}
          onClose={() => setEditShotKey(null)}
          onPreview={(src, isVideo, label) => setMediaPreview({ src, isVideo, label })}
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
  onPreview?: (src: string, isVideo: boolean, label: string) => void
  loading?: boolean
  cssAspectRatio?: string
}

function stripScenePrefix(title: string): string {
  return title.replace(/^\s*场景\s*\d+\s*[:：、\-]?\s*/, '').trim()
}

function SceneCard({ scene, sceneIdx, sceneKey, hoveredKey, onHover, onEdit, onEditShot, onRefreshFrame, onPreview, loading = false, cssAspectRatio = '16 / 9' }: SceneCardProps): JSX.Element {
  const isHovered = hoveredKey === sceneKey
  const cleanTitle = stripScenePrefix(scene.title) || `场景${sceneIdx + 1}`

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
        <button className="script-card-edit-btn scene-pill-edit" onClick={onEdit} title="编辑">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </button>
      </div>
      <div className="script-card-item-divider" />

      {loading ? (
        <div className="scene-loading">
          <div className="scene-loading-icon">✦</div>
          <div className="scene-loading-text">正在创作</div>
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
              onPreview={onPreview}
            />
          ))}
      </div>

      <div className="script-card-item-divider" />

      <div className="storyboard-section-title">场景预览</div>
      <div className="scene-composited-video">
        {scene.compositedPreview ? (
          <ImageWithPlaceholder
            src={scene.compositedPreview}
            alt="场景预览"
            status="generated"
            style={{ aspectRatio: cssAspectRatio, width: '100%', borderRadius: '6px', objectFit: 'cover', cursor: 'pointer' }}
            onClick={() => onPreview?.(scene.compositedVideo || scene.compositedPreview!, true, '场景预览')}
          />
        ) : scene.compositedVideo ? (
          <FrameCard
            label=""
            src={scene.compositedVideo}
            previewSrc={scene.compositedPreview}
            frameKey={`${sceneKey}-composited`}
            hoveredKey={hoveredKey}
            onHover={onHover}
            isVideo
            frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
            onClick={() => onPreview?.(scene.compositedVideo!, true, '场景预览')}
          />
        ) : (
          <ImageWithPlaceholder
            src=""
            alt="场景预览"
            status="waiting"
            style={{ aspectRatio: cssAspectRatio, width: '100%', borderRadius: '6px', objectFit: 'cover' }}
          />
        )}
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
  onPreview?: (src: string, isVideo: boolean, label: string) => void
}

function stripShotPrefix(title?: string): string {
  if (!title) return ''
  return title.replace(/^\s*镜\s*头?\s*\d+\s*[:：、\-]?\s*/, '').trim()
}

function ShotCard({ shot, shotIdx, shotKey, hoveredKey, onHover, cssAspectRatio = '16 / 9', onEdit, onRefreshFrame, onPreview }: ShotCardProps): JSX.Element {
  const isHovered = hoveredKey === shotKey
  const cleanTitle = stripShotPrefix(shot.title) || `镜头${shotIdx + 1}`
  return (
    <div
      className={`shot-card${isHovered ? ' card-hovered' : ''}`}
      onMouseEnter={() => onHover(shotKey)}
      onMouseLeave={() => onHover(null)}
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
            onRefresh={shot.firstFramePrompt ? () => onRefreshFrame?.('firstFrame', shot.firstFramePrompt!) : undefined}
            onClick={() => onPreview?.(shot.firstFrame, false, '起始帧')}
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
            onRefresh={shot.lastFramePrompt ? () => onRefreshFrame?.('lastFrame', shot.lastFramePrompt!) : undefined}
            onClick={() => onPreview?.(shot.lastFrame, false, '结束帧')}
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
            onClick={() => onPreview?.(shot.video, true, '动态分镜')}
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

  if (hideLast) return <div className={`shot-card-frame${className ? ' ' + className : ''}`} />

  const handleClick = () => {
    if (onClick && !isPlaceholder) {
      onClick()
    }
  }

  return (
    <div
      className={`shot-card-frame${isHovered ? ' card-hovered' : ''}${className ? ' ' + className : ''}`}
      onMouseEnter={() => onHover(frameKey)}
      onMouseLeave={() => onHover(null)}
      onClick={handleClick}
    >
      {label && <span className="shot-card-image-label">{label}</span>}
      {isVideo ? (
        isPlaceholder ? (
          <ImageWithPlaceholder
            key={src}
            src={src}
            alt={label}
            status={status || 'waiting'}
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
          status={status || (isPlaceholder ? 'waiting' : 'generated')}
          className="shot-card-img"
          style={frameStyle}
        />
      )}
      {onRefresh && (
        <button className="frame-refresh-btn" onClick={(e) => { e.stopPropagation(); onRefresh() }} title="重新生成">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      )}
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
  onRefreshFrame?: (sceneIdx: number, shotIdx: number, frameType: 'firstFrame' | 'lastFrame', prompt: string) => void
  onClose: () => void
  onPreview?: (src: string, isVideo: boolean, label: string) => void
}

function ShotEditor({ shot, cssAspectRatio, sceneIdx, shotIdx, onRefreshFrame, onClose, onPreview }: ShotEditorProps): JSX.Element {
  const cleanTitle = stripShotPrefix(shot.title) || `镜头${shotIdx + 1}`
  return (
    <div className="story-editor-backdrop" onClick={onClose}>
      <div className="shot-editor-dialog" onClick={e => e.stopPropagation()}>
        <div className="story-editor-header">
          <div className="story-editor-title">编辑镜头 — {cleanTitle}</div>
          <div className="story-editor-actions">
            <button className="story-editor-btn" onClick={onClose} title="关闭">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
        <div className="story-editor-divider" />
        <div className="shot-editor-body">
          <div className="shot-editor-desc">
            <div className="shot-card-row">
              <span className="shot-card-tag">[视觉描述]</span>
              <span className="shot-card-text">{shot.visualDescription}</span>
            </div>
            <div className="shot-card-row">
              <span className="shot-card-tag">[对白音效]</span>
              <span className="shot-card-text">{shot.voiceDescription}</span>
            </div>
          </div>
          <div className="shot-editor-frames">
            <FrameCard
              label="起始帧"
              src={shot.firstFrame}
              frameKey={`edit-shot-${sceneIdx}-${shotIdx}-frame-0`}
              hoveredKey={null}
              onHover={() => {}}
              frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
              onRefresh={shot.firstFramePrompt ? () => onRefreshFrame?.(sceneIdx, shotIdx, 'firstFrame', shot.firstFramePrompt!) : undefined}
              onClick={() => onPreview?.(shot.firstFrame, false, '起始帧')}
              status={shot.firstFrameStatus}
            />
            <FrameCard
              label="结束帧"
              src={shot.lastFrame}
              frameKey={`edit-shot-${sceneIdx}-${shotIdx}-frame-1`}
              hoveredKey={null}
              onHover={() => {}}
              frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
              onRefresh={shot.lastFramePrompt ? () => onRefreshFrame?.(sceneIdx, shotIdx, 'lastFrame', shot.lastFramePrompt!) : undefined}
              onClick={() => onPreview?.(shot.lastFrame, false, '结束帧')}
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
              onClick={() => onPreview?.(shot.video, true, '动态分镜')}
              status={shot.videoStatus}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default ShootingScriptCard
