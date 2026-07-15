import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useProjectStore } from '../../../stores/projectStore'

function SceneScriptsNode({ selected }: NodeProps) {
  const scenes = useProjectStore(s => s.scenes)
  const status = useProjectStore(s => s.pipelineStatus?.steps?.scene_scripts?.status || 'pending')
  return (
    <div className={`canvas-node scene-scripts-node${selected ? ' selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="canvas-node-header">
        <span className="canvas-node-icon">📜</span>
        分场剧本 ({scenes.length})
      </div>
      <div className="canvas-node-body">
        {scenes.length === 0 ? (
          <span className="canvas-node-empty">等待生成</span>
        ) : (
          <div className="canvas-scene-list">
            {scenes.slice(0, 3).map((s, i) => (
              <div key={i} className="canvas-scene-item">
                <span className="canvas-scene-idx">#{i + 1}</span>
                <span>{s.title || `场景 ${i + 1}`}</span>
              </div>
            ))}
            {scenes.length > 3 && (
              <div className="canvas-scene-more">+{scenes.length - 3}</div>
            )}
          </div>
        )}
        <div className="canvas-node-status-row">
          <span className={`canvas-node-status-dot ${status === 'running' || status === 'generating' ? 'running' : status}`} />
          <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 10 }}>
            {status === 'completed' ? '已完成' : status === 'running' || status === 'generating' ? '生成中' : '待处理'}
          </span>
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

export default memo(SceneScriptsNode)
