import { useState, useRef, useEffect, useCallback } from 'react'
import ImageWithPlaceholder from './ImageWithPlaceholder'
import { useEscClose } from './useEscClose'
import './CharacterCard.css'

export interface CharacterPortraits {
  front: string
  side: string
  back: string
}

export type PortraitViewStatus = 'waiting' | 'generating' | 'generated' | 'error'

export interface PortraitStatus {
  front: PortraitViewStatus
  side: PortraitViewStatus
  back: PortraitViewStatus
}

export type PortraitView = 'front' | 'side' | 'back'

export interface CharacterData {
  name: string
  staticFeatures: string
  dynamicFeatures: string
  portraits: CharacterPortraits
  sourceUrl?: string
  portraitStatus?: PortraitStatus
  portraitDescriptions?: Record<PortraitView, string>
}

interface CharacterCardProps {
  characters: CharacterData[]
  aspectRatio: string
  loading?: boolean
  disabled?: boolean
  statusMessage?: string

  onRegenerate?: () => void
  onCharacterUpdate?: (idx: number, data: CharacterData) => void
  onRefreshImage?: (characterIdx: number, view: string) => string | void
}

function getHeightRatio(aspectRatio: string): number {
  const parts = aspectRatio.split(':')
  if (parts.length === 2) {
    const w = parseFloat(parts[0])
    const h = parseFloat(parts[1])
    if (w > 0) return h / w
  }
  return 1
}

const PHOTO_WIDTH = 180
const VIEW_LABELS: Record<string, string> = { front: '正面', side: '侧面', back: '背面' }

function CharacterCard({ characters, aspectRatio, loading = false, disabled = false, statusMessage, onRegenerate, onCharacterUpdate, onRefreshImage }: CharacterCardProps): JSX.Element {
  const [editIdx, setEditIdx] = useState<number | null>(null)
  const [lightbox, setLightbox] = useState<{ charIdx: number; viewIdx: number } | null>(null)

  const photoHeight = PHOTO_WIDTH * getHeightRatio(aspectRatio)

  const views: Array<{ key: keyof CharacterPortraits; label: string }> = [
    { key: 'front', label: '正面' },
    { key: 'side',  label: '侧面' },
    { key: 'back',  label: '背面' },
  ]

  const lightboxChar = lightbox != null ? characters[lightbox.charIdx] : null
  const lightboxView = lightbox != null ? views[lightbox.viewIdx] : null
  const lightboxSrc = lightboxChar && lightboxView ? lightboxChar.portraits[lightboxView.key] : ''

  const navigateLightbox = useCallback((dir: -1 | 1) => {
    if (!lightbox) return
    let { charIdx, viewIdx } = lightbox
    viewIdx += dir
    if (viewIdx < 0) {
      charIdx--
      viewIdx = views.length - 1
    } else if (viewIdx >= views.length) {
      charIdx++
      viewIdx = 0
    }
    if (charIdx < 0 || charIdx >= characters.length) return
    setLightbox({ charIdx, viewIdx })
  }, [lightbox, characters.length])

  useEffect(() => {
    if (!lightbox) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') navigateLightbox(-1)
      else if (e.key === 'ArrowRight') navigateLightbox(1)
      else if (e.key === 'Escape') setLightbox(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [lightbox, navigateLightbox])

  return (
    <div className="character-card">
      <div className="character-card-header">
        <div className="character-card-title">角色造型</div>
        {!loading && characters.length > 0 && (
          <div className="character-card-actions">
            <button className="story-link story-link-disabled" title="编辑" disabled>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
            <span className="story-link-sep">|</span>
            <span className="story-link story-link-disabled" title="编辑">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </span>
          </div>
        )}
      </div>
      <div className="character-card-divider" />
      {loading ? (
        <div key="loading" className="character-card-loading">
          <div className="character-card-loading-icon">✦</div>
          <div className="character-card-loading-text">{statusMessage || '正在创作'}</div>
        </div>
      ) : characters.length === 0 ? (
        <div key="empty" className="character-card-empty">
          <div className="character-card-empty-text">暂无人物的描述</div>
        </div>
      ) : (
        <div key="data" className="character-card-scroll">
          <div className="character-card-track">
            {characters.map((char, idx) => (
              <div key={idx} className="character-card-item" style={{ animationDelay: `${idx * 0.08}s` }}>
                <h3 className="character-card-name">{char.name}</h3>
                <button className="character-card-edit-btn" onClick={() => setEditIdx(idx)} title="编辑">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                <div className="character-card-features">
                  <div className="character-card-feature-row">
                    <span className="character-card-feature-label">静态特征</span>
                    <span className="character-card-feature-text">{char.staticFeatures}</span>
                  </div>
                  <div className="character-card-feature-row">
                    <span className="character-card-feature-label">动态特征</span>
                    <span className="character-card-feature-text">{char.dynamicFeatures}</span>
                  </div>
                </div>
                <div className="character-card-photos">
                  {views.map(({ key }, vi) => (
                    <div key={key} className="character-card-photo" style={{ width: PHOTO_WIDTH, height: photoHeight }}>
                      <ImageWithPlaceholder
                        key={char.portraits[key]}
                        src={char.portraits[key]}
                        alt={`${char.name} ${key}`}
                        status={char.portraitStatus?.[key] ?? (char.portraits?.[key] ? 'generated' : 'waiting')}
                        width={PHOTO_WIDTH}
                        height={photoHeight}
                        onClick={char.portraits[key] ? () => setLightbox({ charIdx: idx, viewIdx: vi }) : undefined}
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {editIdx !== null && (
        <CharacterEditor
          character={characters[editIdx]}
          aspectRatio={aspectRatio}
          onSave={(data) => onCharacterUpdate?.(editIdx, data)}
          onClose={() => setEditIdx(null)}
          onRefreshImage={(view) => onRefreshImage?.(editIdx, view)}
          onLightbox={(view) => setLightbox({ charIdx: editIdx, viewIdx: views.findIndex(v => v.key === view) })}
        />
      )}

      {lightbox && lightboxChar && lightboxView && (
        <div className="character-lightbox" onClick={() => setLightbox(null)}>
          <div className="character-lightbox-content" onClick={e => e.stopPropagation()}>
            <img src={lightboxSrc} alt={`${lightboxChar.name} ${lightboxView.label}`} />
            <div className="character-lightbox-label">{lightboxChar.name} — {lightboxView.label}</div>
            <button className="character-lightbox-close" onClick={() => setLightbox(null)}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
            {(lightbox.charIdx > 0 || lightbox.viewIdx > 0) && (
              <button className="character-lightbox-nav character-lightbox-nav--left" onClick={() => navigateLightbox(-1)}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </button>
            )}
            {(lightbox.charIdx < characters.length - 1 || lightbox.viewIdx < views.length - 1) && (
              <button className="character-lightbox-nav character-lightbox-nav--right" onClick={() => navigateLightbox(1)}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

interface CharacterEditorProps {
  character: CharacterData
  aspectRatio: string
  onSave: (data: CharacterData) => void
  onClose: () => void
  onRefreshImage?: (view: string) => string | void | Promise<string | void>
  onLightbox?: (view: string) => void
}

function CharacterEditor({ character, aspectRatio, onSave, onClose, onRefreshImage, onLightbox }: CharacterEditorProps): JSX.Element {
  const [staticFeatures, setStaticFeatures] = useState(character.staticFeatures)
  const [dynamicFeatures, setDynamicFeatures] = useState(character.dynamicFeatures)
  const savedRef = useRef({ staticFeatures: character.staticFeatures, dynamicFeatures: character.dynamicFeatures })
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout>>()
  useEscClose(onClose)

  const dirty = staticFeatures !== savedRef.current.staticFeatures || dynamicFeatures !== savedRef.current.dynamicFeatures

  const showToast = (msg: string) => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 2000)
  }

  const handleSave = () => {
    savedRef.current = { staticFeatures, dynamicFeatures }
    onSave({ ...character, staticFeatures, dynamicFeatures })
    showToast('保存成功')
  }

  const handleRefreshImage = async (view: string) => {
    const msg = await onRefreshImage?.(view)
    if (msg) {
      showToast(msg)
    } else {
      showToast(`${VIEW_LABELS[view] || view} 图片重新生成中...`)
    }
  }

  function toCssAspectRatio(aspectRatio: string): string {
    return aspectRatio.replace(':', ' / ')
  }

  return (
    <div className="story-editor-backdrop">
      <div className="character-editor-dialog" onClick={e => e.stopPropagation()}>
        <div className="story-editor-header">
          <div className="story-editor-title">编辑 - {character.name}</div>
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

        <div className="character-editor-body">
          <div className="character-editor-row">
            <div className="character-editor-row-label">静态特征</div>
            <textarea className="character-editor-textarea" rows={3} value={staticFeatures} onChange={e => setStaticFeatures(e.target.value)} />
          </div>

          <div className="character-editor-row" style={{ marginTop: '8px' }}>
            <div className="character-editor-row-label">动态特征</div>
            <textarea className="character-editor-textarea" rows={3} value={dynamicFeatures} onChange={e => setDynamicFeatures(e.target.value)} />
          </div>

          <div className="character-editor-row" style={{ marginTop: '14px' }}>
            <div className="character-editor-row-label">人物肖像</div>
            <div className="character-editor-photos-wrap">
              <div className="character-editor-photos-row">
                {(['front', 'side', 'back'] as const).map((view) => (
                  <div key={view} className="character-editor-photo-col">
                    <div className="character-editor-photo" style={{ aspectRatio: toCssAspectRatio(aspectRatio) }}>
                      <ImageWithPlaceholder
                        key={character.portraits[view]}
                        src={character.portraits[view]}
                        alt={VIEW_LABELS[view]}
                        status={character.portraitStatus?.[view] || (character.portraits?.[view] ? 'generated' : 'waiting')}
                        onClick={character.portraits[view] ? () => onLightbox?.(view) : undefined}
                      />
                      {(character.portraitStatus?.[view] === 'generated' || character.portraitStatus?.[view] === 'error') && (
                        <button className={`character-editor-photo-refresh${character.portraitStatus?.[view] === 'error' ? ' character-editor-photo-refresh--error' : ''}`} onClick={() => handleRefreshImage(view)} title={`重新生成${VIEW_LABELS[view]}图`}>
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="23 4 23 10 17 10" />
                            <polyline points="1 20 1 14 7 14" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      {toast && <div className="story-editor-toast">{toast}</div>}
    </div>
  )
}

export default CharacterCard
