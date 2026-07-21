import { useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import Markdown from './Markdown'
import { useEscClose } from './useEscClose'
import { useCreationStore } from './stores/creationStore'
import './SceneScriptsCard.css'

export interface SceneScriptScene {
  title: string
  content: string
}

function SceneEditor({ idx, scene, onSave, onClose }: { idx: number; scene: SceneScriptScene; onSave: (idx: number, data: { title: string; content: string }) => void; onClose: () => void }): JSX.Element {
  const [title, setTitle] = useState(scene.title)
  const [content, setContent] = useState(scene.content)
  const savedRef = useRef({ title: scene.title, content: scene.content })
  const dirty = title !== savedRef.current.title || content !== savedRef.current.content
  useEscClose(onClose)

  const handleSave = () => {
    onSave(idx, { title, content })
    savedRef.current = { title, content }
    onClose()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      if (dirty) handleSave()
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
      <div className="scene-editor-dialog" onClick={e => e.stopPropagation()}>
        <div className="story-editor-header">
          <div className="story-editor-title">编辑 — {scene.title || `场景${idx + 1}`}</div>
          <div className="story-editor-actions">
            <button
              className={`story-editor-btn story-editor-btn-save${!dirty ? ' story-editor-btn-disabled' : ''}`}
              onClick={handleSave}
              disabled={!dirty}
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
        <div className="scene-editor-body">
          <div className="scene-editor-row">
            <div className="scene-editor-row-label">标题</div>
            <input className="scene-editor-input" value={title} onChange={e => setTitle(e.target.value)} onKeyDown={handleKeyDown} />
          </div>
          <div className="scene-editor-row">
            <div className="scene-editor-row-label">内容</div>
            <textarea className="scene-editor-textarea" value={content} onChange={e => setContent(e.target.value)} onKeyDown={handleKeyDown} />
          </div>
        </div>
        <div className="story-editor-footer">
          <span className="story-editor-hint">⌘Enter 保存 · Esc 关闭</span>
        </div>
      </div>
    </div>
  )

  return createPortal(dialog, document.body)
}

function SceneScriptsCard(): JSX.Element {
  const scenes = useCreationStore(s => s.scenes)
  const refreshingSceneScripts = useCreationStore(s => s.refreshingSceneScripts)
  const stepStatuses = useCreationStore(s => s.stepStatuses)
  const loading = refreshingSceneScripts || stepStatuses?.scene_scripts === 1

  const [editIdx, setEditIdx] = useState<number | null>(null)
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

  const handleItemMouseMove = useCallback((e: React.MouseEvent) => {
    const item = (e.target as HTMLElement).closest('.scene-scripts-card-item')
    if (!item) return
    const rect = item.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width * 100).toFixed(1)
    const y = ((e.clientY - rect.top) / rect.height * 100).toFixed(1)
    ;(item as HTMLElement).style.setProperty('--glow-x', `${x}%`)
    ;(item as HTMLElement).style.setProperty('--glow-y', `${y}%`)
  }, [])

  const handleItemMouseLeave = useCallback((e: React.MouseEvent) => {
    const item = (e.target as HTMLElement).closest('.scene-scripts-card-item')
    if (!item) return
    ;(item as HTMLElement).style.setProperty('--glow-x', '50%')
    ;(item as HTMLElement).style.setProperty('--glow-y', '50%')
  }, [])

  const handleSave = (idx: number, data: { title: string; content: string }) => {
    useCreationStore.getState().handleSceneScriptEdit(idx, data)
  }

  const handleRefresh = useCallback(() => {
    useCreationStore.getState().handleRefreshSceneScripts()
  }, [])

  return (
    <div className="scene-scripts-card" ref={cardRef} onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave}>
      <div className="scene-scripts-card-header">
        <div className="scene-scripts-card-title">
          <span className="scene-scripts-card-title-pill">分场剧本</span>
        </div>
        {!loading && scenes.length > 0 && (
          <div className="scene-scripts-card-actions">
            <button className="story-link" title="刷新" onClick={handleRefresh}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="scene-scripts-card-body-area">
        <div className="scene-scripts-card-body">
          {scenes.length === 0 && !loading ? (
            <div className="scene-scripts-card-empty">暂无可用的场景</div>
          ) : scenes.length === 0 ? null : (
            <ul className="scene-scripts-card-list" onMouseMove={handleItemMouseMove} onMouseLeave={handleItemMouseLeave}>
              {scenes.map((scene, idx) => {
                const cleanTitle = scene.title || `场景${idx + 1}`
                return (
                  <li key={idx} className="scene-scripts-card-item">
                    <div className="scene-scripts-card-item-index">
                      <span className="scene-scripts-card-item-index-num">{String(idx + 1).padStart(2, '0')}</span>
                      <span className="scene-scripts-card-item-index-title">{cleanTitle}</span>
                    </div>
                    <button className="scene-scripts-card-edit-btn" onClick={() => setEditIdx(idx)} title="编辑">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                    </button>
                    <div className="scene-scripts-card-item-content"><Markdown content={scene.content.replace(/\\n/g, '\n')} /></div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
        <div className={`scene-scripts-card-loading-overlay${loading ? ' active' : ''}`}>
          <div className="scene-scripts-card-loading-icon">✦</div>
          <div className="scene-scripts-card-loading-text">正在创作</div>
        </div>
      </div>
      {editIdx !== null && scenes[editIdx] && (
        <SceneEditor
          idx={editIdx}
          scene={scenes[editIdx]}
          onSave={handleSave}
          onClose={() => setEditIdx(null)}
        />
      )}
    </div>
  )
}

export default SceneScriptsCard
