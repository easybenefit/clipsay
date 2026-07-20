import { useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import Markdown from './Markdown'
import { useEscClose } from './useEscClose'
import { useCreationStore } from './stores/creationStore'
import './StoryCard.css'

function StoryCard(): JSX.Element {
  const output = useCreationStore(s => s.output)
  const storyTitle = useCreationStore(s => s.storyTitle)
  const error = useCreationStore(s => s.error)
  const creating = useCreationStore(s => s.creating)
  const status = (useCreationStore(s => s.stepStatuses)?.story ?? 0)
  const loading = status === 1 || (status === 0 && creating)
  const stepFailed = status === 3

  const [showEditor, setShowEditor] = useState(false)
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

  const handleSave = (text: string) => {
    useCreationStore.getState().saveProjectData({ story: text })
  }

  const handleRegenerate = useCallback(() => {
    useCreationStore.getState().handleRegenerateStoryboard()
  }, [])

  return (
    <div className="story-card" ref={cardRef} onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave}>
      <div className="story-card-header">
        <div className="story-card-title">
          <span className="story-card-title-pill">故事  ·  {storyTitle || '故事'}</span>
        </div>
        {!loading && (
          <div className="story-card-actions">
            <button className={`story-link${loading || showEditor ? ' story-link-disabled' : ''}`} onClick={() => !loading && setShowEditor(true)} title="编辑">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
            <span className="story-link-sep">|</span>
            <button className={`story-link${loading || showEditor ? ' story-link-disabled' : ''}`} onClick={() => !loading && handleRegenerate()} title="重新创作">
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

      {stepFailed ? (
        <div className="story-card-body story-card-error">
          <div className="story-card-error-icon">⚠</div>
          <div className="story-card-error-text">{error || '故事生成失败'}</div>
        </div>
      ) : loading ? (
        <div className="story-card-loading">
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
        <div className="story-card-body">
            <div className="story-card-content"><Markdown content={output || ''} /></div>
        </div>
      )}

      {showEditor && (
        <StoryEditor
          initialContent={output || ''}
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      if (dirty && !saving) handleSave()
    }
  }

  // Lock body scroll
  const bodyLockRef = useRef(false)
  if (!bodyLockRef.current) {
    document.body.style.overflow = 'hidden'
    bodyLockRef.current = true
  }

  const dialog = (
    <div className="story-editor-backdrop" onClick={onClose}>
      <div className="story-editor-dialog" onClick={e => e.stopPropagation()}>
        <div className="story-editor-header">
          <div className="story-editor-title">编辑故事</div>
          <div className="story-editor-actions">
            <button
              className={`story-editor-btn story-editor-btn-save${!dirty || saving ? ' story-editor-btn-disabled' : ''}`}
              onClick={handleSave}
              disabled={!dirty || saving}
              title="保存 (⌘Enter)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>保存</span>
            </button>
            <button className="story-editor-btn" onClick={onClose} title="关闭 (Esc)">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
        <textarea
          className="story-editor-textarea"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        <div className="story-editor-footer">
          <span className="story-editor-hint">⌘Enter 保存 · Esc 关闭</span>
        </div>
      </div>
      {toast && <div className="story-editor-toast">{toast}</div>}
    </div>
  )

  // Cleanup body scroll on unmount
  const cleanupRef = useRef(false)
  if (!cleanupRef.current) {
    const timer = setTimeout(() => { cleanupRef.current = true }, 0)
    return createPortal(dialog, document.body)
  }

  return createPortal(dialog, document.body)
}

export default StoryCard
