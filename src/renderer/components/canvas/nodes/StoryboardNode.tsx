import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useProjectStore } from '../../../stores/projectStore'

function StoryboardNode({ selected }: NodeProps) {
  const scenes = useProjectStore(s => s.scenes)
  const totalShots = scenes.reduce((sum, s) => sum + (s.shots?.length || 0), 0)
  const hasFrames = scenes.some(s => s.shots?.some(sh => sh.firstFrame || sh.lastFrame))
  const status = useProjectStore(s => s.pipelineStatus?.steps?.storyboard?.status || 'pending')
  return (
    <div className={`canvas-node storyboard-node${selected ? ' selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="canvas-node-header">
        <span className="canvas-node-icon">🎨</span>
        分镜设计
      </div>
      <div className="canvas-node-body">
        {totalShots === 0 ? (
          <span className="canvas-node-empty">等待生成</span>
        ) : (
          <div className="canvas-shot-counts">
            <span>场景 {scenes.length}</span>
            <span>镜头 {totalShots}</span>
            <span>帧 {hasFrames ? '✓' : '–'}</span>
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

export default memo(StoryboardNode)
