export interface SizeOption {
  id: string
  label: string
  width: number
  height: number
  labelCn: string
}

export const SIZE_OPTIONS: SizeOption[] = [
  { id: '1:1',  label: '1:1',  width: 1024, height: 1024, labelCn: '正方形' },
  { id: '4:3',  label: '4:3',  width: 1024, height: 768,  labelCn: '横版' },
  { id: '3:4',  label: '3:4',  width: 768,  height: 1024, labelCn: '竖版' },
  { id: '16:9', label: '16:9', width: 1024, height: 576,  labelCn: '宽屏横版' },
  { id: '9:16', label: '9:16', width: 576,  height: 1024, labelCn: '竖屏' },
]

export const DEFAULT_SIZE_MAP: Record<string, string> = {
  '1:1': '1024x1024',
  '4:3': '1024x768',
  '3:4': '768x1024',
  '16:9': '1024x576',
  '9:16': '576x1024',
}

const SIZE_TIER_MULTIPLIER: Record<string, number> = {
  '1K': 1,
  '2K': 2,
  '3K': 3,
  '4K': 4,
}

export function getSizeString(ratioId: string, sizeMap: Record<string, string>, sizeTier?: string): string {
  const base = sizeMap[ratioId] || '1024x1024'
  if (!sizeTier || sizeTier === '1K') return base
  const mul = SIZE_TIER_MULTIPLIER[sizeTier] || 1
  const [w, h] = base.split('x').map(Number)
  return `${w * mul}x${h * mul}`
}

export function toCssAspectRatio(ratioId: string): string {
  const opt = SIZE_OPTIONS.find(o => o.id === ratioId)
  if (!opt) return '16 / 9'
  return `${opt.width} / ${opt.height}`
}
