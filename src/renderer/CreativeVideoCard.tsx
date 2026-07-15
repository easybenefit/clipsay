import { useState } from 'react'
import { toCssAspectRatio } from './sizeConfig'
import { FrameCard, MediaPreview, type MediaPreviewData, type SceneData } from './ShootingScriptCard'
import './ShootingScriptCard.css'

interface CreativeVideoCardProps {
  scenes: SceneData[]
  aspectRatio?: string
  finalVideo?: string
  finalPreview?: string
}

function CreativeVideoCard({ scenes, aspectRatio = '16:9', finalVideo, finalPreview }: CreativeVideoCardProps): JSX.Element {
  const cssAspectRatio = toCssAspectRatio(aspectRatio)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [mediaPreview, setMediaPreview] = useState<MediaPreviewData | null>(null)

  const hasVideo = !!(finalVideo || scenes.some(s => s.compositedVideo))

  return (
    <div className="script-card">
      <div className="script-card-header">
        <div className="script-card-title">成片</div>
      </div>
      <div className="script-card-divider" />
      {!hasVideo ? (
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
                  onClick={() => setMediaPreview({ items: [{ src: finalVideo, isVideo: true, label: '成片' }], currentIndex: 0 })}
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
