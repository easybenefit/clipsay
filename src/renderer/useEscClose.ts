import { useEffect, useRef } from 'react'

export function useEscClose(onClose: () => void, active: boolean = true) {
  const savedCallback = useRef(onClose)
  savedCallback.current = onClose

  useEffect(() => {
    if (!active) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') savedCallback.current()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [active])
}
