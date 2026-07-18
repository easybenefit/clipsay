import { useState } from 'react'
import { Blurhash } from 'react-blurhash'

export type ImageState = 'waiting' | 'generating' | 'generated' | 'error'

interface ImageWithPlaceholderProps {
  src?: string
  alt: string
  status: ImageState
  width?: number
  height?: number
  className?: string
  style?: React.CSSProperties
  onClick?: () => void
}

const BLURHASH = 'LEHV6nWB2yk8pyo0adR*.7kCMdnj'

const STATUS_STYLE: Record<ImageState, { iconColor: string; bg: string; label: string }> = {
  waiting:    { iconColor: '#b0b0c0', bg: '#18181e', label: '排队中' },
  generating: { iconColor: '#c4b5fd', bg: '#1e1830', label: '生成中' },
  generated:  { iconColor: '#34d399', bg: '#064e3b', label: '' },
  error:      { iconColor: '#f87171', bg: '#2a1515', label: '生成错误' },
}

export default function ImageWithPlaceholder({
  src,
  alt,
  status,
  width,
  height,
  className,
  style,
  onClick,
}: ImageWithPlaceholderProps) {
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError] = useState(false)

  // NOTE: No useEffect resetting imgLoaded/imgError here.
  // The caller uses key={src} so the component is fully re-mounted when src changes.
  // A useEffect would race with a synchronous onLoad (cached image) and
  // reset imgLoaded to false after onLoad set it true, causing the
  // absolutely-positioned Blurhash canvas to permanently cover the <img>.

  const isPending = status === 'waiting' || status === 'generating'
  const hasValidSrc = src && src.length > 0
  const showImg = status === 'generated' && hasValidSrc && !imgError
  const cfg = STATUS_STYLE[status]

  return (
    <div
      className={className}
      onClick={onClick}
      style={{
        position: 'relative',
        width: width || '100%',
        height: height || '100%',
        overflow: 'hidden',
        background: cfg.bg,
        cursor: onClick ? 'pointer' : undefined,
        ...style,
      }}
    >
      {!showImg && (
        <Blurhash
          hash={BLURHASH}
          width="100%"
          height="100%"
          resolutionX={32}
          resolutionY={32}
          punch={1}
        />
      )}

      {!showImg && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            color: cfg.iconColor,
            zIndex: 1,
          }}
        >
          <div
            className={isPending ? 'iwp-ring iwp-ring-pending' : 'iwp-ring'}
            style={{
              width: 48,
              height: 48,
              borderRadius: '50%',
              border: '2px solid currentColor',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span
              className={isPending ? 'iwp-icon iwp-icon-pending' : 'iwp-icon'}
              style={{
                fontSize: '1.5rem',
                lineHeight: 1,
              }}
            >
              ✦
            </span>
          </div>
          <span
            style={{
              fontSize: '0.9rem',
              fontWeight: 500,
              letterSpacing: '0.04em',
              opacity: 0.9,
              textShadow: '0 1px 2px rgba(0,0,0,0.5)',
            }}
          >
            {cfg.label}
          </span>
        </div>
      )}

      {showImg && !imgLoaded && (
        <Blurhash
          hash={BLURHASH}
          width="100%"
          height="100%"
          resolutionX={32}
          resolutionY={32}
          punch={1}
        />
      )}

      {hasValidSrc && (status === 'generated') && (
        <img
          src={src}
          alt={alt}
          onLoad={() => { setImgLoaded(true); setImgError(false) }}
          onError={() => setImgError(true)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: showImg ? 'block' : 'none',
          }}
        />
      )}
    </div>
  )
}
