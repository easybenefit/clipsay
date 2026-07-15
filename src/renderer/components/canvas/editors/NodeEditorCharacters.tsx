import { useState } from 'react'
import { useProjectStore } from '../../../stores/projectStore'

function NodeEditorCharacters() {
  const characters = useProjectStore(s => s.characters)
  const projectId = useProjectStore(s => s.projectId)
  const updateCharacter = useProjectStore(s => s.updateCharacter)
  const saveToBackend = useProjectStore(s => s.saveToBackend)
  const [saving, setSaving] = useState(false)
  const [editingIdx, setEditingIdx] = useState<number | null>(null)

  const handleChange = (idx: number, field: string, value: string) => {
    updateCharacter(idx, { [field]: value })
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
        <h3 className="canvas-editor-title">👤 角色编辑</h3>
        <span className="canvas-editor-badge">{characters.length} 个角色</span>
      </div>
      <div className="canvas-editor-body">
        {characters.length === 0 && (
          <div className="canvas-editor-empty">暂未提取角色</div>
        )}
        {characters.map((c, idx) => (
          <div key={idx} className="canvas-editor-card">
            <div className="canvas-editor-card-header" onClick={() => setEditingIdx(editingIdx === idx ? null : idx)}>
              <span className="canvas-editor-card-name">{c.name || `角色 ${idx + 1}`}</span>
              <span className="canvas-editor-card-toggle">{editingIdx === idx ? '▾' : '▸'}</span>
            </div>
            {editingIdx === idx && (
              <div className="canvas-editor-card-body">
                <label className="canvas-editor-label">名称</label>
                <input
                  className="canvas-editor-input"
                  value={c.name}
                  onChange={e => handleChange(idx, 'name', e.target.value)}
                />
                <label className="canvas-editor-label">外貌特征</label>
                <textarea
                  className="canvas-editor-textarea"
                  rows={3}
                  value={c.staticFeatures}
                  onChange={e => handleChange(idx, 'staticFeatures', e.target.value)}
                />
                <label className="canvas-editor-label">服饰描述</label>
                <textarea
                  className="canvas-editor-textarea"
                  rows={2}
                  value={c.dynamicFeatures}
                  onChange={e => handleChange(idx, 'dynamicFeatures', e.target.value)}
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

export default NodeEditorCharacters
