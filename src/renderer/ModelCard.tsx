import { useState, useRef, useEffect } from 'react'

interface ModelCardProps {
  title: string
  description: string
  model: string
  apiKey: string
  baseUrl: string
  rateLimitMin: string
  rateLimitDay: string
  modelOptions: string[]
  onModelChange: (model: string) => void
  onUpdate: (field: string, value: string) => void
  onSave: () => void
}

const SaveIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

const ChevronIcon = ({ open }: { open: boolean }) => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transition: 'transform 0.35s cubic-bezier(0.32,0.72,0,1)', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>
    <polyline points="6 9 12 15 18 9" />
  </svg>
)

export function ModelSelect({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="cs" ref={ref}>
      <button className={`cs-trigger${open ? ' open' : ''}`} onClick={() => setOpen(p => !p)} type="button">
        <span className="cs-value">{value}</span>
        <ChevronIcon open={open} />
      </button>
      {open && (
        <div className="cs-dropdown">
          {options.map(o => (
            <div key={o} className={`cs-option${o === value ? ' active' : ''}`} onClick={() => { onChange(o); setOpen(false) }}>
              <span>{o}</span>
              {o === value && (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ModelCard(props: ModelCardProps): JSX.Element {
  return (
    <div className="settings-card-outer">
      <div className="settings-card">
        <div className="settings-card-header">
          <span className="settings-card-title">{props.title}</span>
          <span className="settings-card-desc">{props.description}</span>
        </div>
        <div className="settings-field">
          <span>模型</span>
          <ModelSelect options={props.modelOptions} value={props.model} onChange={v => props.onModelChange(v)} />
        </div>
        <div className="settings-field">
          <span>API 密钥</span>
          <input className="settings-input" type="password" value={props.apiKey} onChange={e => props.onUpdate('apiKey', e.target.value)} placeholder="sk-..." />
        </div>
        <div className="settings-field">
          <span>URL 地址</span>
          <input className="settings-input" type="text" value={props.baseUrl} onChange={e => props.onUpdate('baseUrl', e.target.value)} placeholder="https://..." />
        </div>
        <div className="settings-field">
          <span>速率限制</span>
          <div className="settings-rl-inline">
            <div className="settings-rl-row">
              <input className="settings-input" type="text" value={props.rateLimitMin} onChange={e => props.onUpdate('rateLimitMin', e.target.value)} placeholder="500" />
              <span className="settings-rl-label">/ 分钟</span>
            </div>
            <div className="settings-rl-row">
              <input className="settings-input" type="text" value={props.rateLimitDay} onChange={e => props.onUpdate('rateLimitDay', e.target.value)} placeholder="2000" />
              <span className="settings-rl-label">/ 天</span>
            </div>
          </div>
        </div>
        <div className="settings-card-actions">
          <button className="settings-btn-save" onClick={props.onSave}>
            <span>保存</span>
            <span className="btn-icon-wrap"><SaveIcon /></span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default ModelCard