import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useProjectStore } from '../../../stores/projectStore'

function StoryNode({ selected, data }: NodeProps) {
  const output = useProjectStore(s => s.output)
  const status = useProjectStore(s => s.pipelineStatus?.steps?.story?.status || 'pending')
  return (
    <div className={`canvas-node story-node${selected ? ' selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="canvas-node-header">
        <span className="canvas-node-icon">📝</span>
        故事大纲
      </div>
      <div className="canvas-node-body">
        {output ? (
          output.slice(0, 80) + (output.length > 80 ? '…' : '')
        ) : (
          <span className="canvas-node-empty">等待生成</span>
        )}
        <div className="canvas-node-status-row">
          <span className={`canvas-node-status-dot ${status}`} />
          <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 10 }}>
            {status === 'completed' ? '已完成' : status === 'running' ? '生成中' : '待处理'}
          </span>
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

export default memo(StoryNode)
