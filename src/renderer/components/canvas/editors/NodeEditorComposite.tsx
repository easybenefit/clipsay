import { useProjectStore } from '../../../stores/projectStore'

function NodeEditorComposite() {
  const finalPreview = useProjectStore(s => s.finalPreview)
  const finalVideo = useProjectStore(s => s.finalVideo)

  return (
    <div className="canvas-editor">
      <div className="canvas-editor-header">
        <h3 className="canvas-editor-title">✨ 视频合成</h3>
      </div>
      <div className="canvas-editor-body">
        {!finalPreview && !finalVideo && (
          <div className="canvas-editor-empty">暂未生成视频</div>
        )}
        {finalPreview && (
          <div className="canvas-editor-preview-section">
            <h4 className="canvas-editor-subtitle">预览</h4>
            <img src={finalPreview} alt="视频预览" className="canvas-editor-preview-img" />
          </div>
        )}
        {finalVideo && (
          <div className="canvas-editor-preview-section">
            <h4 className="canvas-editor-subtitle">最终视频</h4>
            <video src={finalVideo} controls className="canvas-editor-preview-video" />
          </div>
        )}
      </div>
    </div>
  )
}

export default NodeEditorComposite
