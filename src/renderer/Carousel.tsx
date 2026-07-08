import { useEffect, useState, useCallback, useRef } from 'react'
import './Carousel.css'
import splashMp4 from '../../assets/splash.mp4'

const ITEMS = [
  {
    title: 'Seedance 2.0',
    desc: 'AI 视频生成，前所未有的画质与一致性',
  },
  {
    title: '创作者挑战赛',
    desc: '参与挑战，赢取大奖与曝光机会',
  },
  {
    title: '智能剪辑',
    desc: 'AI 自动识别高光片段，一键成片',
  },
  {
    title: '语音转字幕',
    desc: '精准语音识别，自动生成多语言字幕',
  },
]

function Carousel() {
  const [slide, setSlide] = useState(0)
  const trackRef = useRef<HTMLDivElement>(null)
  const N = ITEMS.length

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
    const timer = setInterval(nextSlide, 6000)
    return () => clearInterval(timer)
  }, [nextSlide])

  const duplicated = [...ITEMS.slice(-1), ...ITEMS, ...ITEMS.slice(0, 2)]
  const centerIdx = slide + 1

  return (
    <div className="carousel">
      <div className="carousel-stage">
        <div className="carousel-track" ref={trackRef} style={{ transform: `translateX(${-(centerIdx - 1) * (100 / 3)}%)` }}>
          {duplicated.map((item, i) => {
            const offset = i - centerIdx
            const pos = offset === 0 ? 'center' : offset === -1 ? 'prev' : offset === 1 ? 'next' : 'hidden'
            const clickHandler = offset === -1 ? prevSlide : offset === 1 ? nextSlide : undefined
            return (
              <div key={i} className={`carousel-slide ${pos}`} onClick={clickHandler}>
                <video className="carousel-video" src={splashMp4} muted autoPlay loop playsInline />
                <svg className="deco" viewBox="0 0 200 200" fill="none">
                  <circle cx="120" cy="100" r="80" stroke="currentColor" strokeWidth="0.5" opacity="0.3" />
                  <circle cx="120" cy="100" r="50" stroke="currentColor" strokeWidth="0.5" opacity="0.2" />
                  <circle cx="120" cy="100" r="20" stroke="currentColor" strokeWidth="0.5" opacity="0.15" />
                </svg>
                <div className="carousel-content">
                  <h2>{item.title}</h2>
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
        {ITEMS.map((_, i) => (
          <button key={i} className={`carousel-dot${i === slide ? ' active' : ''}`} onClick={() => setSlide(i)} />
        ))}
      </div>
    </div>
  )
}

export default Carousel
