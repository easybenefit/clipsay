import { useState, useEffect } from 'react'
import { useProjectStore } from '../../../stores/projectStore'

function NodeEditorStory() {
  const output = useProjectStore(s => s.output)
  const projectId = useProjectStore(s => s.projectId)
  const setOutput = useProjectStore(s => s.setOutput)
  const saveToBackend = useProjectStore(s => s.saveToBackend)
  const [text, setText] = useState(output || '')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setText(output || '')
  }, [output])

  const handleSave = async () => {
    setSaving(true)
    setOutput(text)
    await saveToBackend()
    setSaving(false)
  }

  return (
    <div className="canvas-editor">
      <div className="canvas-editor-header">
        <h3 className="canvas-editor-title">📝 故事大纲</h3>
      </div>
      <div className="canvas-editor-body">
        <textarea
          className="canvas-editor-textarea"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="输入故事内容..."
        />
      </div>
      <div className="canvas-editor-footer">
        <span className="canvas-editor-meta">
          字数: {text.length}
        </span>
        <button className="canvas-editor-btn canvas-editor-btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '💾 保存'}
        </button>
      </div>
    </div>
  )
}

export default NodeEditorStory
