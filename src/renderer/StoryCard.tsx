import { useState, useRef } from 'react'
import Markdown from './Markdown'
import { useEscClose } from './useEscClose'
import './StoryCard.css'

interface StoryCardProps {
  title?: string
  content: string
  loading?: boolean
  regenerating?: boolean
  disabled?: boolean
  onRegenerate: () => void
  onSave?: (content: string) => void
}

function StoryCard({ title, content, loading = false, regenerating = false, disabled = false, onRegenerate, onSave }: StoryCardProps): JSX.Element {
  const [showEditor, setShowEditor] = useState(false)

  const handleSave = (text: string) => {
    onSave?.(text)
  }

  return (
    <div className="story-card">
      <div className="story-card-header">
        <div className="story-card-title">故事</div>
        {!loading && (
          <div className="story-card-actions">
            <button className={`story-link${disabled || showEditor ? ' story-link-disabled' : ''}`} onClick={() => !disabled && onRegenerate()} title="重新创作">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="story-card-divider" />

      {loading ? (
        <div className="story-card-loading">
          <div className="story-card-loading-icon">✦</div>
          <div className="story-card-loading-text">{regenerating ? '正在重新创作' : '正在创作'}</div>
        </div>
      ) : (
        <div className="story-card-body">
            <div className="story-card-body-item">
              <div className="story-card-body-pill">
                <span className="story-card-body-pill-title">{title || '故事'}</span>
              </div>
              {!loading && (
                <button className={`story-card-body-edit${disabled ? ' story-link-disabled' : ''}`} onClick={() => !disabled && setShowEditor(true)} title="编辑">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
              )}
              <div className="story-card-content"><Markdown content={content} /></div>
            </div>
        </div>
      )}

      {showEditor && (
        <StoryEditor
          initialContent={content}
          onSave={handleSave}
          onClose={() => setShowEditor(false)}
        />
      )}
    </div>
  )
}

interface StoryEditorProps {
  initialContent: string
  onSave: (content: string) => void
  onClose: () => void
}

function StoryEditor({ initialContent, onSave, onClose }: StoryEditorProps): JSX.Element {
  const [text, setText] = useState(initialContent)
  const savedRef = useRef(initialContent)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout>>()
  const dirty = text !== savedRef.current
  useEscClose(onClose)

  const showToast = (msg: string) => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 2000)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      onSave(text)
      savedRef.current = text
      showToast('保存成功')
    } catch {
      showToast('保存失败')
    }
    setSaving(false)
  }

  return (
    <div className="story-editor-backdrop">
      <div className="story-editor-dialog" onClick={e => e.stopPropagation()}>
        <div className="story-editor-header">
          <div className="story-editor-title">编辑-故事</div>
          <div className="story-editor-actions">
            <button
              className={`story-editor-btn${!dirty || saving ? ' story-editor-btn-disabled' : ''}`}
              onClick={handleSave}
              disabled={!dirty || saving}
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
        <textarea
          className="story-editor-textarea"
          value={text}
          onChange={e => setText(e.target.value)}
          autoFocus
        />
      </div>
      {toast && <div className="story-editor-toast">{toast}</div>}
    </div>
  )
}

export default StoryCard
