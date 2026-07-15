import { useState } from 'react'
import { useProjectStore } from '../../../stores/projectStore'

function NodeEditorStoryboard() {
  const scenes = useProjectStore(s => s.scenes)
  const updateShot = useProjectStore(s => s.updateShot)
  const saveToBackend = useProjectStore(s => s.saveToBackend)
  const [saving, setSaving] = useState(false)
  const [editingShot, setEditingShot] = useState<{ sceneIdx: number; shotIdx: number } | null>(null)

  const handleChange = (sceneIdx: number, shotIdx: number, field: string, value: string) => {
    updateShot(sceneIdx, shotIdx, { [field]: value })
  }

  const handleSave = async () => {
    setSaving(true)
    await saveToBackend()
    setSaving(false)
    setEditingShot(null)
  }

  const totalShots = scenes.reduce((sum, s) => sum + (s.shots?.length || 0), 0)

  return (
    <div className="canvas-editor">
      <div className="canvas-editor-header">
        <h3 className="canvas-editor-title">🎨 分镜设计</h3>
        <span className="canvas-editor-badge">{totalShots} 个镜头</span>
      </div>
      <div className="canvas-editor-body">
        {totalShots === 0 && (
          <div className="canvas-editor-empty">暂未生成分镜</div>
        )}
        {scenes.map((scene, si) =>
          (scene.shots || []).map((shot, shi) => {
            const key = `s${si}-shot${shi}`
            const isEditing = editingShot?.sceneIdx === si && editingShot?.shotIdx === shi
            return (
              <div key={key} className="canvas-editor-card">
                <div className="canvas-editor-card-header"
                  onClick={() => setEditingShot(isEditing ? null : { sceneIdx: si, shotIdx: shi })}>
                  <span className="canvas-editor-card-name">
                    [{scene.title || `场景${si + 1}`}] {shot.title || `镜头 ${shi + 1}`}
                  </span>
                  <span className="canvas-editor-card-toggle">{isEditing ? '▾' : '▸'}</span>
                </div>
                {isEditing && (
                  <div className="canvas-editor-card-body">
                    <label className="canvas-editor-label">镜头标题</label>
                    <input
                      className="canvas-editor-input"
                      value={shot.title}
                      onChange={e => handleChange(si, shi, 'title', e.target.value)}
                    />
                    <label className="canvas-editor-label">视觉描述</label>
                    <textarea
                      className="canvas-editor-textarea"
                      rows={3}
                      value={shot.visualDescription}
                      onChange={e => handleChange(si, shi, 'visualDescription', e.target.value)}
                    />
                    <label className="canvas-editor-label">音频描述</label>
                    <textarea
                      className="canvas-editor-textarea"
                      rows={2}
                      value={shot.voiceDescription}
                      onChange={e => handleChange(si, shi, 'voiceDescription', e.target.value)}
                    />
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
      <div className="canvas-editor-footer">
        <button className="canvas-editor-btn canvas-editor-btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '💾 保存'}
        </button>
      </div>
    </div>
  )
}

export default NodeEditorStoryboard
