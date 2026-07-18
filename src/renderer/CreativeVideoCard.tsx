import { useState } from 'react'
import { toCssAspectRatio } from './sizeConfig'
import ImageWithPlaceholder from './ImageWithPlaceholder'
import { FrameCard, MediaPreview, type MediaPreviewData, type SceneData } from './ShootingScriptCard'
import './ShootingScriptCard.css'

interface CreativeVideoCardProps {
  scenes: SceneData[]
  aspectRatio?: string
  finalVideo?: string
  finalPreview?: string
  finalVideoStatus?: number
  onRefresh?: () => Promise<void>
}

function CreativeVideoCard({ scenes, aspectRatio = '16:9', finalVideo, finalPreview, finalVideoStatus = 0, onRefresh }: CreativeVideoCardProps): JSX.Element {
  const cssAspectRatio = toCssAspectRatio(aspectRatio)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [mediaPreview, setMediaPreview] = useState<MediaPreviewData | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const hasVideo = !!(finalVideo || scenes.some(s => s.compositedVideo))

  const handleRefresh = async () => {
    if (!onRefresh || refreshing) return
    setRefreshing(true)
    try {
      await onRefresh()
    } catch (e) {
      console.error('[composite_video] refresh failed:', e)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="script-card">
      <div className="script-card-header">
        <div className="script-card-title">TV Show</div>
        {onRefresh && (
          <button
            className={`card-refresh-btn${refreshing ? ' spinning' : ''}`}
            onClick={handleRefresh}
            disabled={refreshing}
            title="重新合成视频"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        )}
      </div>
      <div className="script-card-divider" />
      {!hasVideo && finalVideoStatus !== 1 ? (
        <div className="script-card-empty">
          <div className="script-card-empty-text">暂无可用的视频</div>
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
                  onClick={() => setMediaPreview({ items: [{ src: finalVideo, isVideo: true, label: 'TV Show' }], currentIndex: 0 })}
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
