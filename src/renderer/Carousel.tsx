import { useEffect, useState, useCallback, useRef } from 'react'
import './Carousel.css'
import splashMp4 from '../../assets/splash.mp4'

const DEFAULT_ITEMS = [
  {
    type: 'default' as const,
    title: 'Seedance 2.0',
    desc: 'AI 视频生成，前所未有的画质与一致性',
  },
  {
    type: 'default' as const,
    title: '创作者挑战赛',
    desc: '参与挑战，赢取大奖与曝光机会',
  },
  {
    type: 'default' as const,
    title: '智能剪辑',
    desc: 'AI 自动识别高光片段，一键成片',
  },
  {
    type: 'default' as const,
    title: '语音转字幕',
    desc: '精准语音识别，自动生成多语言字幕',
  },
]

export interface CarouselSlide {
  type: 'project' | 'default'
  projectId?: number
  title: string
  desc: string
  previewUrl?: string
  videoUrl?: string
}

interface CarouselProps {
  slides?: CarouselSlide[]
  onSlideClick?: (projectId: number) => void
}

function Carousel({ slides, onSlideClick }: CarouselProps) {
  const items = slides ?? DEFAULT_ITEMS
  const [slide, setSlide] = useState(0)
  const [erroredImages, setErroredImages] = useState<Set<number>>(new Set())
  const [modalVideo, setModalVideo] = useState<string | null>(null)
  const [isHovered, setIsHovered] = useState(false)
  const trackRef = useRef<HTMLDivElement>(null)
  const N = items.length

  const nextSlide = useCallback(() => setSlide(prev => prev + 1), [])
  const prevSlide = useCallback(() => setSlide(prev => (prev - 1 + N) % N), [N])

  useEffect(() => {
    if (slide >= N) {
      const el = trackRef.current
      if (!el) return
      const onEnd = () => {
        el.style.transition = 'none'
        setSlide(slide - N)
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            el.style.transition = ''
          })
        })
        el.removeEventListener('transitionend', onEnd)
      }
      el.addEventListener('transitionend', onEnd)
      return () => el.removeEventListener('transitionend', onEnd)
    }
  }, [slide, N])

  useEffect(() => {
    if (isHovered) return
    const timer = setInterval(nextSlide, 6000)
    return () => clearInterval(timer)
  }, [nextSlide, isHovered])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setModalVideo(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const duplicated = [...items.slice(-1), ...items, ...items.slice(0, 2)]
  const centerIdx = slide + 1

  return (
    <div className="carousel" onMouseEnter={() => setIsHovered(true)} onMouseLeave={() => setIsHovered(false)}>
      <div className="carousel-stage">
        <div className="carousel-track" ref={trackRef} style={{ transform: `translateX(${-(centerIdx - 1) * (100 / 3)}%)` }}>
          {duplicated.map((item, i) => {
            const offset = i - centerIdx
            const pos = offset === 0 ? 'center' : offset === -1 ? 'prev' : offset === 1 ? 'next' : 'hidden'
            const clickHandler = offset === -1 ? prevSlide : offset === 1 ? nextSlide : () => {
              const videoUrl = item.type === 'default' ? splashMp4 : item.videoUrl
              if (videoUrl) {
                setModalVideo(videoUrl)
              } else if (item.type === 'project' && item.projectId && onSlideClick) {
                onSlideClick(item.projectId)
              }
            }
            return (
              <div key={i} className={`carousel-slide ${pos}`} onClick={clickHandler}>
                {item.type === 'default' ? (
                  <video className="carousel-video" src={splashMp4} muted autoPlay loop playsInline />
                ) : item.videoUrl ? (
                  <video className="carousel-video" src={item.videoUrl} muted autoPlay loop playsInline />
                ) : item.previewUrl && !erroredImages.has(i) ? (
                  <img className="carousel-video" src={item.previewUrl} alt="" draggable={false}
                    onError={() => setErroredImages(prev => new Set([...prev, i]))} />
                ) : (
                  <video className="carousel-video" src={splashMp4} muted autoPlay loop playsInline />
                )}
                <svg className="deco" viewBox="0 0 200 200" fill="none">
                  <circle cx="120" cy="100" r="80" stroke="currentColor" strokeWidth="0.5" opacity="0.3" />
                  <circle cx="120" cy="100" r="50" stroke="currentColor" strokeWidth="0.5" opacity="0.2" />
                  <circle cx="120" cy="100" r="20" stroke="currentColor" strokeWidth="0.5" opacity="0.15" />
                </svg>
                <div className="carousel-content">
                  <p>{item.desc}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
      <button className="carousel-btn carousel-prev" onClick={prevSlide}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>
      </button>
      <button className="carousel-btn carousel-next" onClick={nextSlide}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
      </button>
      <div className="carousel-dots">
        {items.map((_, i) => (
          <button key={i} className={`carousel-dot${i === slide ? ' active' : ''}`} onClick={() => setSlide(i)} />
        ))}
      </div>
      {modalVideo && (
        <div className="carousel-modal-overlay" onClick={() => setModalVideo(null)}>
          <div className="carousel-modal" onClick={e => e.stopPropagation()}>
            <video key={modalVideo} className="carousel-modal-video" src={modalVideo} autoPlay loop playsInline controls />
            <button className="carousel-modal-close" onClick={() => setModalVideo(null)}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Carousel
