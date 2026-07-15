import { useState } from 'react'
import { useProjectStore } from '../../../stores/projectStore'

function NodeEditorSceneScripts() {
  const scenes = useProjectStore(s => s.scenes)
  const updateScene = useProjectStore(s => s.updateScene)
  const saveToBackend = useProjectStore(s => s.saveToBackend)
  const [saving, setSaving] = useState(false)
  const [editingIdx, setEditingIdx] = useState<number | null>(null)

  const handleChange = (idx: number, field: string, value: string) => {
    updateScene(idx, { [field]: value })
  }

  const handleSave = async () => {
    setSaving(true)
    await saveToBackend()
    setSaving(false)
    setEditingIdx(null)
  }

  return (
    <div className="canvas-editor">
      <div className="canvas-editor-header">
        <h3 className="canvas-editor-title">📜 分场剧本</h3>
        <span className="canvas-editor-badge">{scenes.length} 场</span>
      </div>
      <div className="canvas-editor-body">
        {scenes.length === 0 && (
          <div className="canvas-editor-empty">暂未生成剧本</div>
        )}
        {scenes.map((s, idx) => (
          <div key={idx} className="canvas-editor-card">
            <div className="canvas-editor-card-header" onClick={() => setEditingIdx(editingIdx === idx ? null : idx)}>
              <span className="canvas-editor-card-name">{s.title || `场景 ${idx + 1}`}</span>
              <span className="canvas-editor-card-toggle">{editingIdx === idx ? '▾' : '▸'}</span>
            </div>
            {editingIdx === idx && (
              <div className="canvas-editor-card-body">
                <label className="canvas-editor-label">标题</label>
                <input
                  className="canvas-editor-input"
                  value={s.title}
                  onChange={e => handleChange(idx, 'title', e.target.value)}
                />
                <label className="canvas-editor-label">内容</label>
                <textarea
                  className="canvas-editor-textarea"
                  rows={6}
                  value={s.content}
                  onChange={e => handleChange(idx, 'content', e.target.value)}
                />
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="canvas-editor-footer">
        <button className="canvas-editor-btn canvas-editor-btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '💾 保存'}
        </button>
      </div>
    </div>
  )
}

export default NodeEditorSceneScripts
