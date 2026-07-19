import { useState, useRef, useEffect } from 'react'
import type { Project } from './api'

const BASE = 'http://localhost:8765'

const STYLE_LABEL: Record<string, string> = {
  realistic: '写实',
  anime: '动漫',
  cyberpunk: '赛博朋克',
  cinematic: '电影感',
  fantasy: '奇幻',
  minimalist: '极简',
}

const formatDuration = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

interface ProjectCardProps {
  project: Project
  index: number
  onPlay: (url: string) => void
  onEdit: (id: number) => void
  onDuplicate: (id: number) => void
  onOpen: (id: number) => void
  onIncrementClick: (id: number) => void
}

export default function ProjectCard({
  project: p,
  index,
  onPlay,
  onEdit,
  onDuplicate,
  onOpen,
  onIncrementClick,
}: ProjectCardProps) {
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError] = useState(false)
  const [visible, setVisible] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          obs.unobserve(el)
        }
      },
      { rootMargin: '120px' }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const hasVideo = p.final_video && p.final_video.length > 0
  const previewUrl = (p as any).final_preview
    ? ((p as any).final_preview.startsWith(BASE)
        ? (p as any).final_preview
        : `${BASE}${(p as any).final_preview}`)
    : null
  const isRunning = (p as any).pipeline_status === 'running'

  const handleClick = () => {
    if (hasVideo) {
      onIncrementClick(p.id)
      const url = p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}`
      onPlay(url)
    } else {
      onOpen(p.id)
    }
  }

  return (
    <div
      ref={ref}
      className={`project-card${visible ? ' project-card-visible' : ''}`}
      style={{ '--card-index': index } as React.CSSProperties}
      onClick={handleClick}
    >
      <div className="project-thumb">
        {previewUrl && !imgError ? (
          <>
            {!imgLoaded && (
              <div className="project-thumb-skeleton">
                <div className="skeleton-pulse" />
              </div>
            )}
            <img
              className={`project-thumb-img${imgLoaded ? ' loaded' : ''}`}
              src={previewUrl}
              alt=""
              loading="lazy"
              onLoad={() => setImgLoaded(true)}
              onError={() => setImgError(true)}
            />
          </>
        ) : hasVideo ? (
          <div className="project-thumb-fallback">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="project-thumb-icon">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
        ) : (
          <div className="project-thumb-fallback">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="m21 15-5-5L5 21" />
            </svg>
          </div>
        )}

        {hasVideo && (
          <div className="project-thumb-play">
            <div className="play-ring">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </div>
          </div>
        )}

        {isRunning && (
          <div className="project-thumb-badge">
            <span className="badge-dot" />
            生成中
          </div>
        )}

        {p.idea && (
          <div className="project-thumb-idea">{p.idea}</div>
        )}
      </div>

      <div className="project-card-body">
        <div className="project-name" title={(p as any).story_title || p.name || '未命名项目'}>
          {(p as any).story_title || p.name || '未命名项目'}
        </div>
        <div className="project-actions">
          <div className="project-meta">
            {STYLE_LABEL[p.style] || p.style || '写实'}
            {hasVideo && p.duration ? ` · ${formatDuration(p.duration)}` : ''}
          </div>
          <button className="project-btn" onClick={e => { e.stopPropagation(); onEdit(p.id) }} title="编辑">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
          <button className="project-btn" onClick={e => { e.stopPropagation(); onDuplicate(p.id) }} title="复制">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
