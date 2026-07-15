import { memo } from 'react'
import { useProjectStore } from '../../stores/projectStore'
import NodeEditorStory from './editors/NodeEditorStory'
import NodeEditorCharacters from './editors/NodeEditorCharacters'
import NodeEditorSceneScripts from './editors/NodeEditorSceneScripts'
import NodeEditorStoryboard from './editors/NodeEditorStoryboard'
import NodeEditorComposite from './editors/NodeEditorComposite'

function InspectorPanelInner() {
  const selectedNodeId = useProjectStore(s => s.selectedNodeId)
  const stepStatuses = useProjectStore(s => s.stepStatuses)
  const characters = useProjectStore(s => s.characters)
  const scenes = useProjectStore(s => s.scenes)
  const output = useProjectStore(s => s.output)
  const pipelineStatus = useProjectStore(s => s.pipelineStatus)
  const setSelectedNodeId = useProjectStore(s => s.setSelectedNodeId)

  const steps = [
    { key: 'story', label: '故事大纲', icon: '📝' },
    { key: 'characters', label: '角色提取', icon: '👤' },
    { key: 'portraits', label: '角色肖像', icon: '🎭' },
    { key: 'scene_scripts', label: '分场剧本', icon: '📜' },
    { key: 'storyboard', label: '分镜设计', icon: '🎨' },
    { key: 'shot_frames', label: '镜头帧', icon: '🎥' },
    { key: 'composite_video', label: '视频合成', icon: '✨' },
  ]

  const STATUS_LABEL: Record<string, string> = {
    pending: '待处理',
    running: '进行中',
    generating: '进行中',
    completed: '已完成',
    failed: '失败',
    skipped: '跳过',
  }

  if (selectedNodeId) {
    const backBtn = (
      <button className="canvas-editor-back" onClick={() => setSelectedNodeId(null)}>
        ← 返回列表
      </button>
    )
    switch (selectedNodeId) {
      case 'story':
        return <div className="canvas-inspector">{backBtn}<NodeEditorStory /></div>
      case 'characters':
        return <div className="canvas-inspector">{backBtn}<NodeEditorCharacters /></div>
      case 'sceneScripts':
        return <div className="canvas-inspector">{backBtn}<NodeEditorSceneScripts /></div>
      case 'storyboard':
        return <div className="canvas-inspector">{backBtn}<NodeEditorStoryboard /></div>
      case 'composite':
        return <div className="canvas-inspector">{backBtn}<NodeEditorComposite /></div>
    }
  }

  return (
    <div className="canvas-inspector">
      <div className="canvas-inspector-section">
        <h3 className="canvas-inspector-title">流水线状态</h3>
        <div className="canvas-inspector-steps">
          {steps.map(s => {
            const stepState = pipelineStatus?.steps?.[s.key]
            const dbStatusNum = stepStatuses?.[s.key]
            const status = stepState?.status
              || (dbStatusNum !== undefined
                ? (['pending', 'generating', 'completed', 'failed', 'regenerating'][dbStatusNum] || 'pending')
                : 'pending')
            const statusClass = status === 'completed' ? 'inspector-step-done'
              : status === 'running' || status === 'generating' || status === 'regenerating' ? 'inspector-step-running'
              : status === 'failed' ? 'inspector-step-failed'
              : 'inspector-step-pending'
            return (
              <div key={s.key} className={`inspector-step ${statusClass}`}>
                <span className="inspector-step-icon">{s.icon}</span>
                <span className="inspector-step-label">{s.label}</span>
                <span className="inspector-step-status">{STATUS_LABEL[status] || status}</span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="canvas-inspector-section">
        <h3 className="canvas-inspector-title">统计</h3>
        <div className="canvas-inspector-stats">
          <div className="inspector-stat">
            <span className="inspector-stat-label">角色</span>
            <span className="inspector-stat-value">{characters.length}</span>
          </div>
          <div className="inspector-stat">
            <span className="inspector-stat-label">场景</span>
            <span className="inspector-stat-value">{scenes.length}</span>
          </div>
          <div className="inspector-stat">
            <span className="inspector-stat-label">镜头</span>
            <span className="inspector-stat-value">
              {scenes.reduce((sum, s) => sum + (s.shots?.length || 0), 0)}
            </span>
          </div>
          <div className="inspector-stat">
            <span className="inspector-stat-label">故事</span>
            <span className="inspector-stat-value">{output ? `${output.length}字` : '–'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

const InspectorPanel = memo(InspectorPanelInner)
export default InspectorPanel
