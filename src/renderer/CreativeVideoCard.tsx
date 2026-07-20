import { useState, useRef, useCallback } from 'react'
import { toCssAspectRatio } from './sizeConfig'
import ImageWithPlaceholder from './ImageWithPlaceholder'
import { FrameCard, MediaPreview, type MediaPreviewData, type SceneData } from './ShootingScriptCard'
import { useCreationStore } from './stores/creationStore'
import './ShootingScriptCard.css'

function CreativeVideoCard(): JSX.Element {
  const scenes = useCreationStore(s => s.scenes)
  const size = useCreationStore(s => s.size)
  const finalVideo = useCreationStore(s => s.finalVideo)
  const finalPreview = useCreationStore(s => s.finalPreview)
  const finalVideoStatus = useCreationStore(s => s.finalVideoStatus)
  const cssAspectRatio = toCssAspectRatio(size)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [mediaPreview, setMediaPreview] = useState<MediaPreviewData | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const cardRef = useRef<HTMLDivElement>(null)

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const card = cardRef.current
    if (!card) return
    const rect = card.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width * 100).toFixed(1)
    const y = ((e.clientY - rect.top) / rect.height * 100).toFixed(1)
    card.style.setProperty('--glow-x', `${x}%`)
    card.style.setProperty('--glow-y', `${y}%`)
  }, [])

  const handleMouseLeave = useCallback(() => {
    const card = cardRef.current
    if (!card) return
    card.style.setProperty('--glow-x', '50%')
    card.style.setProperty('--glow-y', '50%')
  }, [])

  const hasVideo = !!(finalVideo || scenes.some(s => s.compositedVideo))

  const handleRefresh = async () => {
    if (refreshing) return
    setRefreshing(true)
    try {
      await useCreationStore.getState().compositeFinalVideo()
    } catch (e) {
      console.error('[composite_video] refresh failed:', e)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="script-card creative-video-card" ref={cardRef} onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave}>
      <div className="script-card-header">
        <div className="script-card-title">
          <span className="script-card-title-pill">作品</span>
        </div>
        <div className="card-actions">
          <button
            className={`story-link${refreshing ? ' story-link-disabled' : ''}`}
            onClick={handleRefresh}
            disabled={refreshing}
            title="重新合成视频"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        </div>
      </div>
      {!hasVideo && finalVideoStatus !== 1 && !refreshing ? (
        <div className="script-card-empty">
          <div className="creative-video-empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </div>
          <div className="script-card-empty-text">暂无可用的视频</div>
        </div>
      ) : refreshing ? (
        <div className="story-card-loading creative-video-loading">
          <div className="story-card-skeleton-lines">
            <div className="story-card-skeleton-line" />
            <div className="story-card-skeleton-line" />
            <div className="story-card-skeleton-line" />
            <div className="story-card-skeleton-line" />
            <div className="story-card-skeleton-line" />
            <div className="story-card-skeleton-line" />
            <div className="story-card-skeleton-line" />
            <div className="story-card-skeleton-line" />
          </div>
        </div>
      ) : (
        <div className="script-card-body">
          <div className="creative-video-section">
            {finalVideo ? (
              <div className="creative-video-single">
                <FrameCard
                  label=""
                  src={finalVideo}
                  previewSrc={finalPreview}
                  frameKey="final-video"
                  hoveredKey={hoveredKey}
                  onHover={setHoveredKey}
                  isVideo
                  frameStyle={{ aspectRatio: cssAspectRatio, width: '100%', height: 'auto' }}
                  onClick={() => setMediaPreview({ items: [{ src: finalVideo, isVideo: true, label: '作品' }], currentIndex: 0 })}
                />
              </div>
            ) : finalVideoStatus === 1 || finalVideoStatus === 2 ? (
              <div className="creative-video-single">
                <ImageWithPlaceholder
                  src=""
                  alt="成片"
                  status="generating"
                  style={{ aspectRatio: cssAspectRatio, width: '100%', borderRadius: '6px' }}
                />
              </div>
            ) : (
              <div className="creative-video-grid">
                {scenes.map((scene, idx) => scene.compositedVideo ? (
                  <div key={`cv-${idx}`} className="creative-video-card-wrapper">
                    <div className="shot-pill" style={{ position: 'absolute', top: -1, left: -1, zIndex: 1 }}>
                      <span className="shot-pill-num">{scene.title || `场景${idx + 1}`}</span>
                    </div>
                    <FrameCard
                      label=""
                      src={scene.compositedVideo}
                      previewSrc={scene.compositedPreview}
                      frameKey={`cv-${idx}`}
                      hoveredKey={hoveredKey}
                      onHover={setHoveredKey}
                      isVideo
                      frameStyle={{ aspectRatio: cssAspectRatio, height: 'auto' }}
                      onClick={() => setMediaPreview({ items: [{ src: scene.compositedVideo!, isVideo: true, label: scene.title || `场景${idx + 1}` }], currentIndex: 0 })}
                    />
                  </div>
                ) : null)}
              </div>
            )}
          </div>
        </div>
      )}

      {mediaPreview && (
        <MediaPreview data={mediaPreview} onClose={() => setMediaPreview(null)} />
      )}
    </div>
  )
}

export default CreativeVideoCard
